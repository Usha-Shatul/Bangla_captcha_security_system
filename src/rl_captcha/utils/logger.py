import os
import sys
import json
import time
import numpy as np
from typing import Optional
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import save_json, load_json, ensure_dir


class TrainingLogger:
    def __init__(self, log_dir: str = None, experiment_name: str = "run"):
        self.log_dir = log_dir or os.path.join(os.path.dirname(__file__), "..", "checkpoints")
        self.experiment_name = experiment_name
        self.log_path = os.path.join(self.log_dir, f"{experiment_name}_log.json")
        ensure_dir(self.log_dir)

        self.episodes = []
        self.start_time = time.time()
        self.metrics_history = []

    def log_episode(
        self,
        episode: int,
        reward: float,
        length: int,
        difficulty: int,
        human_acc: float,
        bot_acc: float,
        agent_stats: dict = None,
    ):
        elapsed = time.time() - self.start_time

        entry = {
            "episode": episode,
            "reward": round(reward, 4),
            "length": length,
            "difficulty": difficulty,
            "human_acc": round(human_acc, 4),
            "bot_acc": round(bot_acc, 4),
            "elapsed_sec": round(elapsed, 2),
            "timestamp": datetime.now().isoformat(),
        }

        if agent_stats:
            entry["agent_stats"] = {k: round(v, 6) if isinstance(v, float) else v for k, v in agent_stats.items()}

        self.episodes.append(entry)
        self.metrics_history.append(entry)

        if episode % 10 == 0:
            self._flush()

    def log_eval(self, episode: int, metrics: dict):
        entry = {
            "episode": episode,
            "type": "eval",
            "timestamp": datetime.now().isoformat(),
            **{k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()},
        }
        self.metrics_history.append(entry)

    def log_config(self, config: dict):
        entry = {
            "type": "config",
            "timestamp": datetime.now().isoformat(),
            "config": config,
        }
        self.metrics_history.append(entry)
        self._flush()

    def _flush(self):
        ensure_dir(self.log_dir)
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(self.metrics_history, f, indent=2, ensure_ascii=False)

    def get_summary(self) -> dict:
        if not self.episodes:
            return {}

        rewards = [e["reward"] for e in self.episodes]
        human_accs = [e["human_acc"] for e in self.episodes]
        bot_accs = [e["bot_acc"] for e in self.episodes]
        difficulties = [e["difficulty"] for e in self.episodes]

        return {
            "total_episodes": len(self.episodes),
            "avg_reward_last_50": round(float(np.mean(rewards[-50:])), 4),
            "avg_reward_last_10": round(float(np.mean(rewards[-10:])), 4),
            "max_reward": round(float(max(rewards)), 4),
            "final_human_acc": round(human_accs[-1], 4),
            "final_bot_acc": round(bot_accs[-1], 4),
            "avg_difficulty_last_50": round(float(np.mean(difficulties[-50:])), 2),
            "total_time_sec": round(time.time() - self.start_time, 2),
        }

    def save_summary(self, path: str = None):
        path = path or os.path.join(self.log_dir, f"{self.experiment_name}_summary.json")
        summary = self.get_summary()
        save_json(summary, path)
        return summary

    def load(self, path: str = None):
        path = path or self.log_path
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                self.metrics_history = json.load(f)
            self.episodes = [e for e in self.metrics_history if "type" not in e]
