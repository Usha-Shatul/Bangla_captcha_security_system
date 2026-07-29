import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal, Categorical
from typing import Optional, Tuple, List
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.lstm_network import LSTMActorCritic


class RolloutBuffer:
    def __init__(self, max_size: int = 2048):
        self.max_size = max_size
        self.observations = []
        self.actions = []
        self.log_probs = []
        self.rewards = []
        self.dones = []
        self.values = []
        self.advantages = []
        self.returns = []
        self.hidden_states = []

    def add(self, obs, action, log_prob, reward, done, value, hidden=None):
        self.observations.append(obs)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.dones.append(done)
        self.values.append(value)
        if hidden is not None:
            self.hidden_states.append((hidden[0].clone(), hidden[1].clone()))
        else:
            self.hidden_states.append(None)

    def compute_gae(self, last_value: float, gamma: float = 0.99, lam: float = 0.95):
        rewards = np.array(self.rewards)
        values = np.array(self.values + [last_value])
        dones = np.array(self.dones)

        advantages = np.zeros_like(rewards)
        last_gae = 0.0

        for t in reversed(range(len(rewards))):
            next_value = values[t + 1]
            next_non_terminal = 1.0 - dones[t]
            delta = rewards[t] + gamma * next_value * next_non_terminal - values[t]
            advantages[t] = last_gae = delta + gamma * lam * next_non_terminal * last_gae

        self.advantages = advantages.tolist()
        self.returns = (advantages + np.array(self.values)).tolist()

    def get_batches(self, batch_size: int = 64):
        n = len(self.observations)
        indices = np.arange(n)
        np.random.shuffle(indices)

        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            batch_idx = indices[start:end]

            obs_batch = torch.FloatTensor(np.array([self.observations[i] for i in batch_idx]))
            action_batch = torch.FloatTensor(np.array([self.actions[i] for i in batch_idx]))
            log_prob_batch = torch.FloatTensor(np.array([self.log_probs[i] for i in batch_idx]))
            advantage_batch = torch.FloatTensor(np.array([self.advantages[i] for i in batch_idx]))
            return_batch = torch.FloatTensor(np.array([self.returns[i] for i in batch_idx]))

            yield obs_batch, action_batch, log_prob_batch, advantage_batch, return_batch

    def clear(self):
        self.observations.clear()
        self.actions.clear()
        self.log_probs.clear()
        self.rewards.clear()
        self.dones.clear()
        self.values.clear()
        self.advantages.clear()
        self.returns.clear()
        self.hidden_states.clear()

    def __len__(self):
        return len(self.observations)


class PPOAgent:
    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        hidden_dim: int = 128,
        lstm_dim: int = 64,
        num_lstm_layers: int = 1,
        lr: float = 3e-4,
        gamma: float = 0.99,
        lam: float = 0.95,
        clip_epsilon: float = 0.2,
        entropy_coeff: float = 0.01,
        value_coeff: float = 0.5,
        max_grad_norm: float = 0.5,
        ppo_epochs: int = 10,
        mini_batch_size: int = 64,
        continuous: bool = True,
        action_bounds: Tuple[float, float] = (0.0, 1.0),
        device: str = "cpu",
    ):
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.lam = lam
        self.clip_epsilon = clip_epsilon
        self.entropy_coeff = entropy_coeff
        self.value_coeff = value_coeff
        self.max_grad_norm = max_grad_norm
        self.ppo_epochs = ppo_epochs
        self.mini_batch_size = mini_batch_size
        self.continuous = continuous
        self.action_bounds = action_bounds
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

        self.optimizer = optim.Adam(self.network.parameters(), lr=lr, eps=1e-5)
        self.scheduler = optim.lr_scheduler.StepLR(self.optimizer, step_size=100, gamma=0.95)

        self.buffer = RolloutBuffer()
        self.hidden = self.network.init_hidden(device=self.device)

        self.training_stats = {
            "policy_loss": deque(maxlen=100),
            "value_loss": deque(maxlen=100),
            "entropy": deque(maxlen=100),
            "approx_kl": deque(maxlen=100),
            "clip_fraction": deque(maxlen=100),
            "explained_variance": deque(maxlen=100),
        }

    def select_action(self, obs: np.ndarray, deterministic: bool = False) -> Tuple[float, float, float]:
        with torch.no_grad():
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)

            if self.continuous:
                mean, std, new_hidden = self.network.forward_actor(obs_t, self.hidden)
                if deterministic:
                    action = mean
                    log_prob = torch.zeros(1, device=self.device)
                else:
                    dist = Normal(mean, std)
                    action = dist.sample()
                    action = torch.clamp(action, self.action_bounds[0], self.action_bounds[1])
                    log_prob = dist.log_prob(action).sum(dim=-1)

                value, _ = self.network.forward_critic(obs_t, self.hidden)
                self.hidden = new_hidden

                return (
                    action.cpu().numpy().flatten()[0],
                    log_prob.cpu().item(),
                    value.cpu().item(),
                )
            else:
                logits, _, new_hidden = self.network.forward_actor(obs_t, self.hidden)
                dist = Categorical(logits=logits)
                if deterministic:
                    action = torch.argmax(logits, dim=-1)
                    log_prob = torch.zeros(1, device=self.device)
                else:
                    action = dist.sample()
                    log_prob = dist.log_prob(action)

                value, _ = self.network.forward_critic(obs_t, self.hidden)
                self.hidden = new_hidden

                return (
                    action.cpu().item(),
                    log_prob.cpu().item(),
                    value.cpu().item(),
                )

    def store_transition(self, obs, action, log_prob, reward, done, value):
        self.buffer.add(obs, action, log_prob, reward, done, value, self.hidden)

    def update(self) -> dict:
        if len(self.buffer) == 0:
            return {}

        last_value = 0.0
        self.buffer.compute_gae(last_value, self.gamma, self.lam)

        old_log_probs = torch.FloatTensor(self.buffer.log_probs).to(self.device)
        actions = torch.FloatTensor(self.buffer.actions).to(self.device)

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        total_kl = 0.0
        total_clip_frac = 0.0
        num_updates = 0

        for epoch in range(self.ppo_epochs):
            for batch in self.buffer.get_batches(self.mini_batch_size):
                obs_b, act_b, old_lp_b, adv_b, ret_b = batch
                obs_b = obs_b.to(self.device)
                act_b = act_b.to(self.device)
                old_lp_b = old_lp_b.to(self.device)
                adv_b = adv_b.to(self.device)
                ret_b = ret_b.to(self.device)

                _, new_log_prob, entropy, value, _ = self.network.get_action_and_value(
                    obs_b, hidden=None, action=act_b
                )

                ratio = torch.exp(new_log_prob - old_lp_b)
                surr1 = ratio * adv_b
                surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * adv_b
                policy_loss = -torch.min(surr1, surr2).mean()

                value_loss = nn.MSELoss()(value, ret_b)

                entropy_loss = -entropy.mean()

                loss = policy_loss + self.value_coeff * value_loss + self.entropy_coeff * entropy_loss

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.network.parameters(), self.max_grad_norm)
                self.optimizer.step()

                with torch.no_grad():
                    approx_kl = ((ratio - 1) - torch.log(ratio)).mean().item()
                    clip_frac = ((ratio - 1).abs() > self.clip_epsilon).float().mean().item()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.mean().item()
                total_kl += approx_kl
                total_clip_frac += clip_frac
                num_updates += 1

        self.scheduler.step()
        self.buffer.clear()

        if num_updates > 0:
            self.training_stats["policy_loss"].append(total_policy_loss / num_updates)
            self.training_stats["value_loss"].append(total_value_loss / num_updates)
            self.training_stats["entropy"].append(total_entropy / num_updates)
            self.training_stats["approx_kl"].append(total_kl / num_updates)
            self.training_stats["clip_fraction"].append(total_clip_frac / num_updates)

        return {
            "policy_loss": total_policy_loss / max(num_updates, 1),
            "value_loss": total_value_loss / max(num_updates, 1),
            "entropy": total_entropy / max(num_updates, 1),
            "approx_kl": total_kl / max(num_updates, 1),
            "clip_fraction": total_clip_frac / max(num_updates, 1),
            "lr": self.optimizer.param_groups[0]["lr"],
        }

    def reset_hidden(self):
        self.hidden = self.network.init_hidden(device=self.device)

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        torch.save({
            "network_state_dict": self.network.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "scheduler_state_dict": self.scheduler.state_dict(),
            "obs_dim": self.obs_dim,
            "action_dim": self.action_dim,
            "training_stats": {k: list(v) for k, v in self.training_stats.items()},
        }, path)
        print(f"PPO agent saved: {path}")

    def load(self, path: str):
        checkpoint = torch.load(path, map_location=self.device)
        self.network.load_state_dict(checkpoint["network_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        if "scheduler_state_dict" in checkpoint:
            self.scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
        if "training_stats" in checkpoint:
            for k, v in checkpoint["training_stats"].items():
                self.training_stats[k] = deque(v, maxlen=100)
        print(f"PPO agent loaded: {path}")

    def get_stats(self) -> dict:
        return {k: list(v) for k, v in self.training_stats.items()}
