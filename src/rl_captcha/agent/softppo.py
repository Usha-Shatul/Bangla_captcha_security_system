import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal
from typing import Optional, Tuple
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.lstm_network import LSTMActorCritic


class SoftPPOAgent:
    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        hidden_dim: int = 128,
        lstm_dim: int = 64,
        num_lstm_layers: int = 1,
        lr: float = 3e-4,
        lr_alpha: float = 3e-4,
        gamma: float = 0.99,
        lam: float = 0.95,
        clip_epsilon: float = 0.2,
        clip_epsilon_alpha: float = 0.05,
        entropy_coeff: float = 0.01,
        target_kl: float = 0.02,
        value_coeff: float = 0.5,
        max_grad_norm: float = 0.5,
        ppo_epochs: int = 10,
        mini_batch_size: int = 64,
        adaptive_clip: bool = True,
        continuous: bool = True,
        action_bounds: Tuple[float, float] = (0.0, 1.0),
        damping_coeff: float = 0.1,
        device: str = "cpu",
    ):
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.lam = lam
        self.clip_epsilon = clip_epsilon
        self.clip_epsilon_alpha = clip_epsilon_alpha
        self.entropy_coeff = entropy_coeff
        self.target_kl = target_kl
        self.value_coeff = value_coeff
        self.max_grad_norm = max_grad_norm
        self.ppo_epochs = ppo_epochs
        self.mini_batch_size = mini_batch_size
        self.adaptive_clip = adaptive_clip
        self.continuous = continuous
        self.action_bounds = action_bounds
        self.damping_coeff = damping_coeff
        self.device = torch.device(device)

        self.network = LSTMActorCritic(
            obs_dim=obs_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            lstm_dim=lstm_dim,
            num_lstm_layers=num_lstm_layers,
            continuous=continuous,
            action_bounds=action_bounds,
        ).to(self.device)

        self.value_network = LSTMActorCritic(
            obs_dim=obs_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            lstm_dim=lstm_dim,
            num_lstm_layers=num_lstm_layers,
            continuous=continuous,
            action_bounds=action_bounds,
        ).to(self.device)
        self.value_network.load_state_dict(self.network.state_dict())

        self.actor_optimizer = optim.Adam(self.network.parameters(), lr=lr, eps=1e-5)
        self.critic_optimizer = optim.Adam(self.value_network.parameters(), lr=lr * 2, eps=1e-5)
        self.alpha_optimizer = optim.Adam([torch.tensor(self.clip_epsilon, requires_grad=True)], lr=lr_alpha)

        self.current_clip = clip_epsilon
        self.observations = []
        self.actions = []
        self.log_probs = []
        self.rewards = []
        self.dones = []
        self.values = []
        self.advantages = []
        self.returns = []
        self.hidden = self.network.init_hidden(device=self.device)
        self.value_hidden = self.value_network.init_hidden(device=self.device)

        self.training_stats = {
            "policy_loss": deque(maxlen=100),
            "value_loss": deque(maxlen=100),
            "entropy": deque(maxlen=100),
            "approx_kl": deque(maxlen=100),
            "adaptive_clip": deque(maxlen=100),
            "alpha": deque(maxlen=100),
        }

    def select_action(self, obs: np.ndarray, deterministic: bool = False) -> Tuple[float, float, float]:
        with torch.no_grad():
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)

            mean, std, new_hidden = self.network.forward_actor(obs_t, self.hidden)
            value, new_value_hidden = self.value_network.forward_critic(obs_t, self.value_hidden)

            if deterministic:
                action = mean
                log_prob = torch.zeros(1, device=self.device)
            else:
                dist = Normal(mean, std)
                action = dist.sample()
                action = torch.clamp(action, self.action_bounds[0], self.action_bounds[1])
                log_prob = dist.log_prob(action).sum(dim=-1)

            self.hidden = new_hidden
            self.value_hidden = new_value_hidden

            return (
                action.cpu().numpy().flatten()[0],
                log_prob.cpu().item(),
                value.cpu().item(),
            )

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

    def _adapt_clip_epsilon(self, approx_kl: float):
        if not self.adaptive_clip:
            return

        if approx_kl > self.target_kl * 1.5:
            self.current_clip = max(0.1, self.current_clip * 0.8)
        elif approx_kl < self.target_kl / 1.5:
            self.current_clip = min(0.4, self.current_clip * 1.2)

        self.training_stats["adaptive_clip"].append(self.current_clip)

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

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        total_kl = 0.0
        num_updates = 0
        early_stop = False

        for epoch in range(self.ppo_epochs):
            if early_stop:
                break

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

                _, new_log_prob, entropy, _, _ = self.network.get_action_and_value(
                    obs_b, hidden=None, action=act_b
                )

                ratio = torch.exp(new_log_prob - old_lp_b)
                surr1 = ratio * adv_b
                surr2 = torch.clamp(ratio, 1 - self.current_clip, 1 + self.current_clip) * adv_b
                policy_loss = -torch.min(surr1, surr2).mean()

                self.actor_optimizer.zero_grad()
                policy_loss.backward()
                nn.utils.clip_grad_norm_(self.network.parameters(), self.max_grad_norm)
                self.actor_optimizer.step()

                _, new_values, _, _, _ = self.value_network.get_action_and_value(
                    obs_b, hidden=None, action=act_b
                )
                value_loss = nn.MSELoss()(new_values, ret_b)

                self.critic_optimizer.zero_grad()
                value_loss.backward()
                nn.utils.clip_grad_norm_(self.value_network.parameters(), self.max_grad_norm)
                self.critic_optimizer.step()

                with torch.no_grad():
                    approx_kl = ((ratio - 1) - torch.log(ratio)).mean().item()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.mean().item()
                total_kl += approx_kl
                num_updates += 1

                if approx_kl > self.target_kl * 1.5:
                    early_stop = True
                    break

        self._adapt_clip_epsilon(total_kl / max(num_updates, 1))

        self.observations.clear()
        self.actions.clear()
        self.log_probs.clear()
        self.rewards.clear()
        self.dones.clear()
        self.values.clear()
        self.advantages.clear()
        self.returns.clear()

        self.training_stats["policy_loss"].append(total_policy_loss / max(num_updates, 1))
        self.training_stats["value_loss"].append(total_value_loss / max(num_updates, 1))
        self.training_stats["entropy"].append(total_entropy / max(num_updates, 1))
        self.training_stats["approx_kl"].append(total_kl / max(num_updates, 1))
        self.training_stats["alpha"].append(self.current_clip)

        return {
            "policy_loss": total_policy_loss / max(num_updates, 1),
            "value_loss": total_value_loss / max(num_updates, 1),
            "entropy": total_entropy / max(num_updates, 1),
            "approx_kl": total_kl / max(num_updates, 1),
            "adaptive_clip": self.current_clip,
            "early_stop": early_stop,
        }

    def reset_hidden(self):
        self.hidden = self.network.init_hidden(device=self.device)
        self.value_hidden = self.value_network.init_hidden(device=self.device)

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        torch.save({
            "network_state_dict": self.network.state_dict(),
            "value_network_state_dict": self.value_network.state_dict(),
            "actor_optimizer_state_dict": self.actor_optimizer.state_dict(),
            "critic_optimizer_state_dict": self.critic_optimizer.state_dict(),
            "current_clip": self.current_clip,
            "obs_dim": self.obs_dim,
            "action_dim": self.action_dim,
        }, path)
        print(f"SoftPPO agent saved: {path}")

    def load(self, path: str):
        checkpoint = torch.load(path, map_location=self.device)
        self.network.load_state_dict(checkpoint["network_state_dict"])
        self.value_network.load_state_dict(checkpoint["value_network_state_dict"])
        self.actor_optimizer.load_state_dict(checkpoint["actor_optimizer_state_dict"])
        self.critic_optimizer.load_state_dict(checkpoint["critic_optimizer_state_dict"])
        self.current_clip = checkpoint.get("current_clip", self.clip_epsilon)
        print(f"SoftPPO agent loaded: {path}")

    def get_stats(self) -> dict:
        return {k: list(v) for k, v in self.training_stats.items()}
