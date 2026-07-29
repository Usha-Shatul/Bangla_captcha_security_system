import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Normal, Categorical
import numpy as np
from typing import Optional, Tuple


LOG_STD_MIN = -20
LOG_STD_MAX = 2


class LSTMActorCritic(nn.Module):
    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        hidden_dim: int = 128,
        lstm_dim: int = 64,
        num_lstm_layers: int = 1,
        continuous: bool = True,
        action_bounds: Tuple[float, float] = (0.0, 1.0),
    ):
        super().__init__()
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.hidden_dim = hidden_dim
        self.lstm_dim = lstm_dim
        self.num_lstm_layers = num_lstm_layers
        self.continuous = continuous
        self.action_bounds = action_bounds

        self.obs_encoder = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )

        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=lstm_dim,
            num_layers=num_lstm_layers,
            batch_first=True,
        )

        self.critic_head = nn.Sequential(
            nn.Linear(lstm_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

        if continuous:
            self.actor_mean = nn.Sequential(
                nn.Linear(lstm_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, action_dim),
            )
            self.actor_log_std = nn.Parameter(
                torch.zeros(action_dim, dtype=torch.float32)
            )
        else:
            self.actor_head = nn.Sequential(
                nn.Linear(lstm_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, action_dim),
            )

        self._init_weights()

    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=np.sqrt(2))
                nn.init.constant_(module.bias, 0.0)
            elif isinstance(module, nn.LSTM):
                for name, param in module.named_parameters():
                    if "weight" in name:
                        nn.init.orthogonal_(param)
                    elif "bias" in name:
                        nn.init.constant_(param, 0.0)

        if hasattr(self, "actor_mean"):
            nn.init.orthogonal_(self.actor_mean[-1].weight, gain=0.01)
        if hasattr(self, "critic_head"):
            nn.init.orthogonal_(self.critic_head[-1].weight, gain=1.0)

    def forward_actor(
        self, obs: torch.Tensor, hidden: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
    ) -> Tuple[torch.Tensor, torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        if obs.dim() == 2:
            obs = obs.unsqueeze(1)

        encoded = self.obs_encoder(obs)
        lstm_out, new_hidden = self.lstm(encoded, hidden)
        lstm_out = lstm_out[:, -1, :]

        if self.continuous:
            mean = self.actor_mean(lstm_out)
            log_std = self.actor_log_std.clamp(LOG_STD_MIN, LOG_STD_MAX)
            std = log_std.exp()
            return mean, std, new_hidden
        else:
            logits = self.actor_head(lstm_out)
            return logits, None, new_hidden

    def forward_critic(
        self, obs: torch.Tensor, hidden: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        if obs.dim() == 2:
            obs = obs.unsqueeze(1)

        encoded = self.obs_encoder(obs)
        lstm_out, new_hidden = self.lstm(encoded, hidden)
        lstm_out = lstm_out[:, -1, :]

        value = self.critic_head(lstm_out)
        return value, new_hidden

    def get_action_and_value(
        self,
        obs: torch.Tensor,
        hidden: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
        action: Optional[torch.Tensor] = None,
    ):
        encoded = self.obs_encoder(obs if obs.dim() == 3 else obs.unsqueeze(1))
        lstm_out, new_hidden = self.lstm(encoded, hidden)
        lstm_out = lstm_out[:, -1, :]

        value = self.critic_head(lstm_out)

        if self.continuous:
            mean = self.actor_mean(lstm_out)
            log_std = self.actor_log_std.clamp(LOG_STD_MIN, LOG_STD_MAX)
            std = log_std.exp()
            dist = Normal(mean, std)

            if action is None:
                action = dist.sample()
                action = torch.clamp(action, self.action_bounds[0], self.action_bounds[1])

            log_prob = dist.log_prob(action).sum(dim=-1)
            entropy = dist.entropy().sum(dim=-1)
        else:
            logits = self.actor_head(lstm_out)
            dist = Categorical(logits=logits)

            if action is None:
                action = dist.sample()

            log_prob = dist.log_prob(action)
            entropy = dist.entropy()

        return action, log_prob, entropy, value.squeeze(-1), new_hidden

    def init_hidden(self, batch_size: int = 1, device: torch.device = torch.device("cpu")):
        h = torch.zeros(self.num_lstm_layers, batch_size, self.lstm_dim, device=device)
        c = torch.zeros(self.num_lstm_layers, batch_size, self.lstm_dim, device=device)
        return (h, c)


class LSTMNetwork(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        lstm_dim: int = 64,
        num_layers: int = 1,
        output_dim: Optional[int] = None,
    ):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )
        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=lstm_dim,
            num_layers=num_layers,
            batch_first=True,
        )
        self.head = nn.Linear(lstm_dim, output_dim) if output_dim else None

    def forward(self, x, hidden=None):
        if x.dim() == 2:
            x = x.unsqueeze(1)
        enc = self.encoder(x)
        out, hidden = self.lstm(enc, hidden)
        out = out[:, -1, :]
        if self.head is not None:
            out = self.head(out)
        return out, hidden

    def init_hidden(self, batch_size=1, device=torch.device("cpu")):
        h = torch.zeros(self.lstm.num_layers, batch_size, self.lstm.hidden_size, device=device)
        c = torch.zeros(self.lstm.num_layers, batch_size, self.lstm.hidden_size, device=device)
        return (h, c)
