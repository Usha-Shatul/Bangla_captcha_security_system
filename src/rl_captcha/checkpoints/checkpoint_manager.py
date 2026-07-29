import os
import sys
import json
import shutil
import torch
import numpy as np
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CHECKPOINTS_DIR = os.path.dirname(os.path.abspath(__file__))


class CheckpointManager:
    def __init__(
        self,
        checkpoint_dir: str = None,
        max_checkpoints: int = 10,
        save_best_n: int = 3,
    ):
        self.checkpoint_dir = checkpoint_dir or CHECKPOINTS_DIR
        self.max_checkpoints = max_checkpoints
        self.save_best_n = save_best_n
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        self.index_path = os.path.join(self.checkpoint_dir, "checkpoint_index.json")
        self.index = self._load_index()

    def _load_index(self) -> dict:
        if os.path.isfile(self.index_path):
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "checkpoints": [],
            "best_checkpoints": [],
            "total_saved": 0,
            "last_save": None,
        }

    def _save_index(self):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)

    def save_checkpoint(
        self,
        agent,
        episode: int,
        metrics: dict = None,
        tag: str = "",
        is_best: bool = False,
    ) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_parts = [f"ep{episode}"]
        if tag:
            name_parts.append(tag)
        name_parts.append(timestamp)
        filename = "_".join(name_parts) + ".pt"
        filepath = os.path.join(self.checkpoint_dir, filename)

        save_data = {
            "episode": episode,
            "timestamp": timestamp,
            "metrics": metrics or {},
            "tag": tag,
        }

        if hasattr(agent, "network"):
            save_data["network_state_dict"] = agent.network.state_dict()
        if hasattr(agent, "optimizer"):
            save_data["optimizer_state_dict"] = agent.optimizer.state_dict()
        if hasattr(agent, "scheduler") and agent.scheduler is not None:
            save_data["scheduler_state_dict"] = agent.scheduler.state_dict()
        if hasattr(agent, "value_network"):
            save_data["value_network_state_dict"] = agent.value_network.state_dict()
        if hasattr(agent, "actor_optimizer"):
            save_data["actor_optimizer_state_dict"] = agent.actor_optimizer.state_dict()
        if hasattr(agent, "critic_optimizer"):
            save_data["critic_optimizer_state_dict"] = agent.critic_optimizer.state_dict()
        if hasattr(agent, "generator"):
            save_data["generator_state_dict"] = agent.generator.state_dict()
        if hasattr(agent, "discriminator"):
            save_data["discriminator_state_dict"] = agent.discriminator.state_dict()
        if hasattr(agent, "current_clip"):
            save_data["current_clip"] = agent.current_clip
        if hasattr(agent, "obs_dim"):
            save_data["obs_dim"] = agent.obs_dim
        if hasattr(agent, "action_dim"):
            save_data["action_dim"] = agent.action_dim
        if hasattr(agent, "training_stats"):
            save_data["training_stats"] = {
                k: list(v) for k, v in agent.training_stats.items()
            }

        torch.save(save_data, filepath)

        entry = {
            "path": filepath,
            "episode": episode,
            "timestamp": timestamp,
            "tag": tag,
            "metrics": {k: round(v, 4) if isinstance(v, float) else v for k, v in (metrics or {}).items()},
            "is_best": is_best,
        }

        self.index["checkpoints"].append(entry)
        self.index["total_saved"] += 1
        self.index["last_save"] = filepath

        if is_best:
            self.index["best_checkpoints"].append(entry)
            self.index["best_checkpoints"].sort(
                key=lambda x: x.get("metrics", {}).get("reward", 0), reverse=True
            )
            self.index["best_checkpoints"] = self.index["best_checkpoints"][:self.save_best_n]

        self._prune_old_checkpoints()
        self._save_index()

        print(f"Checkpoint saved: {filepath}")
        return filepath

    def save_best(self, agent, episode: int, metrics: dict = None) -> str:
        filepath = os.path.join(self.checkpoint_dir, "best.pt")
        save_data = {
            "episode": episode,
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "metrics": metrics or {},
            "tag": "best",
        }

        if hasattr(agent, "network"):
            save_data["network_state_dict"] = agent.network.state_dict()
        if hasattr(agent, "optimizer"):
            save_data["optimizer_state_dict"] = agent.optimizer.state_dict()
        if hasattr(agent, "value_network"):
            save_data["value_network_state_dict"] = agent.value_network.state_dict()
        if hasattr(agent, "actor_optimizer"):
            save_data["actor_optimizer_state_dict"] = agent.actor_optimizer.state_dict()
        if hasattr(agent, "critic_optimizer"):
            save_data["critic_optimizer_state_dict"] = agent.critic_optimizer.state_dict()
        if hasattr(agent, "obs_dim"):
            save_data["obs_dim"] = agent.obs_dim
        if hasattr(agent, "action_dim"):
            save_data["action_dim"] = agent.action_dim

        torch.save(save_data, filepath)
        print(f"Best checkpoint saved: {filepath}")
        return filepath

    def save_training_state(
        self,
        agent,
        optimizer_scheduler_states: dict = None,
        extra_data: dict = None,
    ) -> str:
        filepath = os.path.join(self.checkpoint_dir, "training_state.pt")

        save_data = {
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "extra": extra_data or {},
        }

        if hasattr(agent, "network"):
            save_data["network"] = agent.network.state_dict()
        if hasattr(agent, "optimizer"):
            save_data["optimizer"] = agent.optimizer.state_dict()
        if hasattr(agent, "scheduler") and agent.scheduler is not None:
            save_data["scheduler"] = agent.scheduler.state_dict()
        if hasattr(agent, "value_network"):
            save_data["value_network"] = agent.value_network.state_dict()
        if hasattr(agent, "actor_optimizer"):
            save_data["actor_optimizer"] = agent.actor_optimizer.state_dict()
        if hasattr(agent, "critic_optimizer"):
            save_data["critic_optimizer"] = agent.critic_optimizer.state_dict()
        if hasattr(agent, "generator"):
            save_data["generator"] = agent.generator.state_dict()
        if hasattr(agent, "discriminator"):
            save_data["discriminator"] = agent.discriminator.state_dict()
        if hasattr(agent, "current_clip"):
            save_data["current_clip"] = agent.current_clip
        if hasattr(agent, "obs_dim"):
            save_data["obs_dim"] = agent.obs_dim
        if hasattr(agent, "action_dim"):
            save_data["action_dim"] = agent.action_dim
        if hasattr(agent, "training_stats"):
            save_data["training_stats"] = {
                k: list(v) for k, v in agent.training_stats.items()
            }

        if optimizer_scheduler_states:
            save_data.update(optimizer_scheduler_states)

        torch.save(save_data, filepath)
        print(f"Training state saved: {filepath}")
        return filepath

    def load_checkpoint(self, filepath: str, agent=None) -> dict:
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Checkpoint not found: {filepath}")

        checkpoint = torch.load(filepath, map_location="cpu")

        if agent is not None:
            self._restore_agent_state(agent, checkpoint)

        print(f"Checkpoint loaded: {filepath}")
        return checkpoint

    def load_best(self, agent=None) -> dict:
        filepath = os.path.join(self.checkpoint_dir, "best.pt")
        return self.load_checkpoint(filepath, agent)

    def load_latest(self, agent=None) -> dict:
        if not self.index["checkpoints"]:
            raise FileNotFoundError("No checkpoints found in index")

        latest = self.index["checkpoints"][-1]
        return self.load_checkpoint(latest["path"], agent)

    def load_training_state(self, agent=None) -> dict:
        filepath = os.path.join(self.checkpoint_dir, "training_state.pt")
        return self.load_checkpoint(filepath, agent)

    def _restore_agent_state(self, agent, checkpoint: dict):
        if "network_state_dict" in checkpoint and hasattr(agent, "network"):
            agent.network.load_state_dict(checkpoint["network_state_dict"])
        elif "network" in checkpoint and hasattr(agent, "network"):
            agent.network.load_state_dict(checkpoint["network"])

        if "optimizer_state_dict" in checkpoint and hasattr(agent, "optimizer"):
            agent.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        elif "optimizer" in checkpoint and hasattr(agent, "optimizer"):
            agent.optimizer.load_state_dict(checkpoint["optimizer"])

        if "scheduler_state_dict" in checkpoint and hasattr(agent, "scheduler") and agent.scheduler is not None:
            agent.scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
        elif "scheduler" in checkpoint and hasattr(agent, "scheduler") and agent.scheduler is not None:
            agent.scheduler.load_state_dict(checkpoint["scheduler"])

        if "value_network_state_dict" in checkpoint and hasattr(agent, "value_network"):
            agent.value_network.load_state_dict(checkpoint["value_network_state_dict"])
        elif "value_network" in checkpoint and hasattr(agent, "value_network"):
            agent.value_network.load_state_dict(checkpoint["value_network"])

        if "actor_optimizer_state_dict" in checkpoint and hasattr(agent, "actor_optimizer"):
            agent.actor_optimizer.load_state_dict(checkpoint["actor_optimizer_state_dict"])
        elif "actor_optimizer" in checkpoint and hasattr(agent, "actor_optimizer"):
            agent.actor_optimizer.load_state_dict(checkpoint["actor_optimizer"])

        if "critic_optimizer_state_dict" in checkpoint and hasattr(agent, "critic_optimizer"):
            agent.critic_optimizer.load_state_dict(checkpoint["critic_optimizer_state_dict"])
        elif "critic_optimizer" in checkpoint and hasattr(agent, "critic_optimizer"):
            agent.critic_optimizer.load_state_dict(checkpoint["critic_optimizer"])

        if "generator_state_dict" in checkpoint and hasattr(agent, "generator"):
            agent.generator.load_state_dict(checkpoint["generator_state_dict"])
        elif "generator" in checkpoint and hasattr(agent, "generator"):
            agent.generator.load_state_dict(checkpoint["generator"])

        if "discriminator_state_dict" in checkpoint and hasattr(agent, "discriminator"):
            agent.discriminator.load_state_dict(checkpoint["discriminator_state_dict"])
        elif "discriminator" in checkpoint and hasattr(agent, "discriminator"):
            agent.discriminator.load_state_dict(checkpoint["discriminator"])

        if "current_clip" in checkpoint and hasattr(agent, "current_clip"):
            agent.current_clip = checkpoint["current_clip"]

        if "training_stats" in checkpoint and hasattr(agent, "training_stats"):
            from collections import deque
            for k, v in checkpoint["training_stats"].items():
                if k in agent.training_stats:
                    agent.training_stats[k] = deque(v, maxlen=100)
                else:
                    agent.training_stats[k] = deque(v, maxlen=100)

    def _prune_old_checkpoints(self):
        checkpoints = self.index["checkpoints"]
        best_paths = set(b["path"] for b in self.index["best_checkpoints"])
        best_pt = os.path.join(self.checkpoint_dir, "best.pt")

        non_best = [c for c in checkpoints if c["path"] not in best_paths and c["path"] != best_pt]

        if len(non_best) > self.max_checkpoints:
            to_remove = non_best[: len(non_best) - self.max_checkpoints]
            for entry in to_remove:
                if os.path.isfile(entry["path"]):
                    os.remove(entry["path"])
                if entry in self.index["checkpoints"]:
                    self.index["checkpoints"].remove(entry)

    def list_checkpoints(self) -> list[dict]:
        return self.index["checkpoints"]

    def get_best(self) -> list[dict]:
        return self.index["best_checkpoints"]

    def get_latest_path(self) -> Optional[str]:
        if self.index["checkpoints"]:
            return self.index["checkpoints"][-1]["path"]
        return None

    def get_best_path(self) -> Optional[str]:
        best = os.path.join(self.checkpoint_dir, "best.pt")
        if os.path.isfile(best):
            return best
        return None

    def delete_checkpoint(self, filepath: str):
        if os.path.isfile(filepath):
            os.remove(filepath)
        self.index["checkpoints"] = [
            c for c in self.index["checkpoints"] if c["path"] != filepath
        ]
        self.index["best_checkpoints"] = [
            c for c in self.index["best_checkpoints"] if c["path"] != filepath
        ]
        self._save_index()
        print(f"Deleted checkpoint: {filepath}")

    def clear_all(self):
        for entry in self.index["checkpoints"]:
            if os.path.isfile(entry["path"]):
                os.remove(entry["path"])

        best = os.path.join(self.checkpoint_dir, "best.pt")
        if os.path.isfile(best):
            os.remove(best)

        ts = os.path.join(self.checkpoint_dir, "training_state.pt")
        if os.path.isfile(ts):
            os.remove(ts)

        self.index = {
            "checkpoints": [],
            "best_checkpoints": [],
            "total_saved": 0,
            "last_save": None,
        }
        self._save_index()
        print("All checkpoints cleared")

    def get_info(self) -> dict:
        total_size = 0
        for entry in self.index["checkpoints"]:
            if os.path.isfile(entry["path"]):
                total_size += os.path.getsize(entry["path"])

        best_pt = os.path.join(self.checkpoint_dir, "best.pt")
        if os.path.isfile(best_pt):
            total_size += os.path.getsize(best_pt)

        return {
            "total_checkpoints": len(self.index["checkpoints"]),
            "best_checkpoints": len(self.index["best_checkpoints"]),
            "total_saved": self.index["total_saved"],
            "last_save": self.index["last_save"],
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "directory": self.checkpoint_dir,
        }


_manager_instance: Optional[CheckpointManager] = None


def get_checkpoint_manager(
    checkpoint_dir: str = None,
    max_checkpoints: int = 10,
) -> CheckpointManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = CheckpointManager(
            checkpoint_dir=checkpoint_dir,
            max_checkpoints=max_checkpoints,
        )
    return _manager_instance
