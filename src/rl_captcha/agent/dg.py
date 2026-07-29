import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal
from typing import Tuple, Optional
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.lstm_network import LSTMNetwork


class GeneratorNetwork(nn.Module):
    def __init__(self, state_dim: int, noise_dim: int, hidden_dim: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim + noise_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, state_dim),
        )
        self.state_dim = state_dim

    def forward(self, state: torch.Tensor, noise: torch.Tensor) -> torch.Tensor:
        x = torch.cat([state, noise], dim=-1)
        return self.net(x)


class DiscriminatorNetwork(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

    def forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        x = torch.cat([state, action], dim=-1)
        return self.net(x)


class DualGeneratorAgent:
    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        hidden_dim: int = 128,
        lstm_dim: int = 64,
        noise_dim: int = 32,
        lr_actor: float = 3e-4,
        lr_critic: float = 3e-4,
        lr_generator: float = 1e-4,
        lr_discriminator: float = 1e-4,
        gamma: float = 0.99,
        lam: float = 0.95,
        clip_epsilon: float = 0.2,
        entropy_coeff: float = 0.01,
        value_coeff: float = 0.5,
        adversarial_coeff: float = 0.5,
        max_grad_norm: float = 0.5,
        ppo_epochs: int = 10,
        mini_batch_size: int = 64,
        action_bounds: Tuple[float, float] = (0.0, 1.0),
        device: str = "cpu",
    ):
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.noise_dim = noise_dim
        self.gamma = gamma
        self.lam = lam
        self.clip_epsilon = clip_epsilon
        self.entropy_coeff = entropy_coeff
        self.value_coeff = value_coeff
        self.adversarial_coeff = adversarial_coeff
        self.max_grad_norm = max_grad_norm
        self.ppo_epochs = ppo_epochs
        self.mini_batch_size = mini_batch_size
        self.action_bounds = action_bounds
        self.device = torch.device(device)

        self.actor = LSTMNetwork(
            input_dim=obs_dim,
            hidden_dim=hidden_dim,
            lstm_dim=lstm_dim,
            num_layers=1,
            output_dim=action_dim * 2,
        ).to(self.device)

        self.critic = LSTMNetwork(
            input_dim=obs_dim,
            hidden_dim=hidden_dim,
            lstm_dim=lstm_dim,
            num_layers=1,
            output_dim=1,
        ).to(self.device)

        self.generator = GeneratorNetwork(
            state_dim=obs_dim,
            noise_dim=noise_dim,
            hidden_dim=hidden_dim,
        ).to(self.device)

        self.discriminator = DiscriminatorNetwork(
            state_dim=obs_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
        ).to(self.device)

        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=lr_actor, eps=1e-5)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=lr_critic, eps=1e-5)
        self.gen_optimizer = optim.Adam(self.generator.parameters(), lr=lr_generator)
        self.disc_optimizer = optim.Adam(self.discriminator.parameters(), lr=lr_discriminator)

        self.observations = []
        self.actions = []
        self.log_probs = []
        self.rewards = []
        self.dones = []
        self.values = []
        self.advantages = []
        self.returns = []

        self.actor_hidden = self.actor.init_hidden(device=self.device)
        self.critic_hidden = self.critic.init_hidden(device=self.device)

        self.training_stats = {
            "actor_loss": deque(maxlen=100),
            "critic_loss": deque(maxlen=100),
            "generator_loss": deque(maxlen=100),
            "discriminator_loss": deque(maxlen=100),
            "adversarial_reward": deque(maxlen=100),
        }

    def select_action(self, obs: np.ndarray, deterministic: bool = False) -> Tuple[float, float, float]:
        with torch.no_grad():
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)

            actor_out, new_actor_hidden = self.actor(obs_t, self.actor_hidden)
            mean, log_std = torch.chunk(actor_out, 2, dim=-1)
            log_std = log_std.clamp(-20, 2)
            std = log_std.exp()

            value_out, new_critic_hidden = self.critic(obs_t, self.critic_hidden)
            value = value_out.squeeze(-1)

            self.actor_hidden = new_actor_hidden
            self.critic_hidden = new_critic_hidden

            if deterministic:
                action = mean
                log_prob = torch.zeros(1, device=self.device)
            else:
                dist = Normal(mean, std)
                action = dist.sample()
                action = torch.clamp(action, self.action_bounds[0], self.action_bounds[1])
                log_prob = dist.log_prob(action).sum(dim=-1)

            return (
                action.cpu().numpy().flatten()[0],
                log_prob.cpu().item(),
                value.cpu().item(),
            )

    def compute_adversarial_reward(self, obs: np.ndarray, action: float) -> float:
        with torch.no_grad():
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
            act_t = torch.FloatTensor([action]).unsqueeze(0).to(self.device)
            fake_prob = self.discriminator(obs_t, act_t)
            return fake_prob.cpu().item()

    def generate_augmented_state(self, obs: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
            noise = torch.randn(1, self.noise_dim).to(self.device)
            augmented = self.generator(obs_t, noise)
            return augmented.cpu().numpy().flatten()

    def store_transition(self, obs, action, log_prob, reward, done, value):
        self.observations.append(obs)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.dones.append(done)
        self.values.append(value)

    def _compute_gae(self, last_value: float):
        rewards = np.array(self.rewards)
        values = np.array(self.values + [last_value])
        dones = np.array(self.dones)

        advantages = np.zeros_like(rewards)
        last_gae = 0.0

        for t in reversed(range(len(rewards))):
            next_value = values[t + 1]
            next_non_terminal = 1.0 - dones[t]
            delta = rewards[t] + self.gamma * next_value * next_non_terminal - values[t]
            advantages[t] = last_gae = delta + self.gamma * self.lam * next_non_terminal * last_gae

        self.advantages = advantages.tolist()
        self.returns = (advantages + np.array(self.values)).tolist()

    def update(self) -> dict:
        if len(self.observations) == 0:
            return {}

        last_value = 0.0
        self._compute_gae(last_value)

        obs_arr = np.array(self.observations)
        act_arr = np.array(self.actions)
        old_lp_arr = np.array(self.log_probs)
        adv_arr = np.array(self.advantages)
        ret_arr = np.array(self.returns)

        adv_mean = adv_arr.mean()
        adv_std = adv_arr.std() + 1e-8
        adv_arr = (adv_arr - adv_mean) / adv_std

        total_actor_loss = 0.0
        total_critic_loss = 0.0
        total_gen_loss = 0.0
        total_disc_loss = 0.0
        total_adv_reward = 0.0
        num_updates = 0

        for epoch in range(self.ppo_epochs):
            indices = np.arange(len(obs_arr))
            np.random.shuffle(indices)

            for start in range(0, len(indices), self.mini_batch_size):
                end = min(start + self.mini_batch_size, len(indices))
                batch_idx = indices[start:end]

                obs_b = torch.FloatTensor(obs_arr[batch_idx]).to(self.device)
                act_b = torch.FloatTensor(act_arr[batch_idx]).to(self.device)
                old_lp_b = torch.FloatTensor(old_lp_arr[batch_idx]).to(self.device)
                adv_b = torch.FloatTensor(adv_arr[batch_idx]).to(self.device)
                ret_b = torch.FloatTensor(ret_arr[batch_idx]).to(self.device)

                actor_out, _ = self.actor(obs_b, hidden=None)
                mean, log_std = torch.chunk(actor_out, 2, dim=-1)
                log_std = log_std.clamp(-20, 2)
                std = log_std.exp()
                dist = Normal(mean, std)
                new_log_prob = dist.log_prob(act_b).sum(dim=-1)
                entropy = dist.entropy().sum(dim=-1)

                ratio = torch.exp(new_log_prob - old_lp_b)
                surr1 = ratio * adv_b
                surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * adv_b
                policy_loss = -torch.min(surr1, surr2).mean() - self.entropy_coeff * entropy.mean()

                self.actor_optimizer.zero_grad()
                policy_loss.backward()
                nn.utils.clip_grad_norm_(self.actor.parameters(), self.max_grad_norm)
                self.actor_optimizer.step()

                value_out, _ = self.critic(obs_b, hidden=None)
                value = value_out.squeeze(-1)
                value_loss = nn.MSELoss()(value, ret_b)

                self.critic_optimizer.zero_grad()
                value_loss.backward()
                nn.utils.clip_grad_norm_(self.critic.parameters(), self.max_grad_norm)
                self.critic_optimizer.step()

                noise = torch.randn(len(batch_idx), self.noise_dim).to(self.device)
                fake_state = self.generator(obs_b, noise)
                fake_actions, _, _ = self.actor(obs_b.detach(), hidden=None)
                fake_action_mean = torch.chunk(fake_actions, 2, dim=-1)[0]

                real_labels = torch.ones(len(batch_idx), 1).to(self.device)
                fake_labels = torch.zeros(len(batch_idx), 1).to(self.device)

                real_pred = self.discriminator(obs_b, act_b)
                fake_pred = self.discriminator(obs_b.detach(), fake_action_mean.detach())

                disc_loss = (
                    nn.BCELoss()(real_pred, real_labels) +
                    nn.BCELoss()(fake_pred, fake_labels)
                ) / 2

                self.disc_optimizer.zero_grad()
                disc_loss.backward()
                self.disc_optimizer.step()

                fake_pred_gen = self.discriminator(obs_b, fake_action_mean)
                gen_loss = nn.BCELoss()(fake_pred_gen, real_labels)

                self.gen_optimizer.zero_grad()
                gen_loss.backward()
                self.gen_optimizer.step()

                total_actor_loss += policy_loss.item()
                total_critic_loss += value_loss.item()
                total_gen_loss += gen_loss.item()
                total_disc_loss += disc_loss.item()
                total_adv_reward += fake_pred.mean().item()
                num_updates += 1

        self.observations.clear()
        self.actions.clear()
        self.log_probs.clear()
        self.rewards.clear()
        self.dones.clear()
        self.values.clear()
        self.advantages.clear()
        self.returns.clear()

        self.actor_hidden = self.actor.init_hidden(device=self.device)
        self.critic_hidden = self.critic.init_hidden(device=self.device)

        self.training_stats["actor_loss"].append(total_actor_loss / max(num_updates, 1))
        self.training_stats["critic_loss"].append(total_critic_loss / max(num_updates, 1))
        self.training_stats["generator_loss"].append(total_gen_loss / max(num_updates, 1))
        self.training_stats["discriminator_loss"].append(total_disc_loss / max(num_updates, 1))
        self.training_stats["adversarial_reward"].append(total_adv_reward / max(num_updates, 1))

        return {
            "actor_loss": total_actor_loss / max(num_updates, 1),
            "critic_loss": total_critic_loss / max(num_updates, 1),
            "generator_loss": total_gen_loss / max(num_updates, 1),
            "discriminator_loss": total_disc_loss / max(num_updates, 1),
            "adversarial_reward": total_adv_reward / max(num_updates, 1),
        }

    def reset_hidden(self):
        self.actor_hidden = self.actor.init_hidden(device=self.device)
        self.critic_hidden = self.critic.init_hidden(device=self.device)

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        torch.save({
            "actor_state_dict": self.actor.state_dict(),
            "critic_state_dict": self.critic.state_dict(),
            "generator_state_dict": self.generator.state_dict(),
            "discriminator_state_dict": self.discriminator.state_dict(),
            "obs_dim": self.obs_dim,
            "action_dim": self.action_dim,
        }, path)
        print(f"DualGenerator agent saved: {path}")

    def load(self, path: str):
        checkpoint = torch.load(path, map_location=self.device)
        self.actor.load_state_dict(checkpoint["actor_state_dict"])
        self.critic.load_state_dict(checkpoint["critic_state_dict"])
        self.generator.load_state_dict(checkpoint["generator_state_dict"])
        self.discriminator.load_state_dict(checkpoint["discriminator_state_dict"])
        print(f"DualGenerator agent loaded: {path}")

    def get_stats(self) -> dict:
        return {k: list(v) for k, v in self.training_stats.items()}
