import os
import json
import numpy as np
from typing import Optional
from collections import deque


class RunningMeanStd:
    def __init__(self, shape: tuple = ()):
        self.mean = np.zeros(shape, dtype=np.float64)
        self.var = np.ones(shape, dtype=np.float64)
        self.count = 1e-4

    def update(self, batch: np.ndarray):
        batch_mean = np.mean(batch, axis=0)
        batch_var = np.var(batch, axis=0)
        batch_count = batch.shape[0]
        self.update_from_moments(batch_mean, batch_var, batch_count)

    def update_from_moments(self, batch_mean, batch_var, batch_count):
        delta = batch_mean - self.mean
        total = self.count + batch_count
        new_mean = self.mean + delta * batch_count / total
        m_a = self.var * self.count
        m_b = batch_var * batch_count
        m2 = m_a + m_b + delta ** 2 * self.count * batch_count / total
        self.mean = new_mean
        self.var = m2 / total
        self.count = total

    def normalize(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / np.sqrt(self.var + 1e-8)

    def save(self, path: str):
        np.savez(path, mean=self.mean, var=self.var, count=self.count)

    def load(self, path: str):
        data = np.load(path)
        self.mean = data["mean"]
        self.var = data["var"]
        self.count = float(data["count"])


class RewardNormalizer:
    def __init__(self, gamma: float = 0.99):
        self.return_rms = RunningMeanStd(shape=())
        self.returns = 0.0
        self.gamma = gamma
        self.ret = 0.0

    def normalize(self, reward: float, done: bool) -> float:
        self.ret = self.ret * self.gamma + reward
        self.return_rms.update(np.array([self.ret]))
        if done:
            self.ret = 0.0
        return reward / np.sqrt(self.return_rms.var + 1e-8)

    def save(self, path: str):
        self.return_rms.save(path)

    def load(self, path: str):
        self.return_rms.load(path)


class ObservationNormalizer:
    def __init__(self, obs_dim: int, epsilon: float = 1e-8):
        self.obs_dim = obs_dim
        self.rms = RunningMeanStd(shape=(obs_dim,))
        self.epsilon = epsilon

    def normalize(self, obs: np.ndarray) -> np.ndarray:
        self.rms.update(obs.reshape(1, -1))
        return (obs - self.rms.mean) / np.sqrt(self.rms.var + self.epsilon)

    def normalize_batch(self, obs: np.ndarray) -> np.ndarray:
        return (obs - self.rms.mean) / np.sqrt(self.rms.var + self.epsilon)

    def save(self, path: str):
        self.rms.save(path)

    def load(self, path: str):
        self.rms.load(path)


class MetricTracker:
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metrics = {}

    def update(self, key: str, value: float):
        if key not in self.metrics:
            self.metrics[key] = deque(maxlen=self.window_size)
        self.metrics[key].append(value)

    def update_dict(self, d: dict):
        for k, v in d.items():
            if isinstance(v, (int, float)):
                self.update(k, v)

    def get(self, key: str) -> float:
        if key in self.metrics and self.metrics[key]:
            return float(np.mean(self.metrics[key]))
        return 0.0

    def get_all(self) -> dict:
        return {k: float(np.mean(v)) for k, v in self.metrics.items() if v}

    def get_std(self, key: str) -> float:
        if key in self.metrics and len(self.metrics[key]) > 1:
            return float(np.std(self.metrics[key]))
        return 0.0

    def reset(self):
        self.metrics.clear()

    def to_dict(self) -> dict:
        return {k: list(v) for k, v in self.metrics.items()}

    def save(self, path: str):
        data = {k: list(v) for k, v in self.metrics.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            self.metrics[k] = deque(v, maxlen=self.window_size)
