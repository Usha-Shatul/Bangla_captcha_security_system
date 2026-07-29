import os
import sys
import numpy as np
from typing import Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from environment.state import StateBuilder
from environment.reward import RewardFunction
from environment.security_actions import SECURITY_ACTIONS, action_to_difficulty, action_name, NUM_ACTIONS


class CaptchaEnv:
    def __init__(
        self,
        state_dim: int = 20,
        num_actions: int = NUM_ACTIONS,
        max_steps: int = 100,
        max_attempts_per_episode: int = 3,
        bot_threshold: float = 0.7,
        reward_config: dict = None,
    ):
        self.state_dim = state_dim
        self.num_actions = num_actions
        self.max_steps = max_steps
        self.max_attempts_per_episode = max_attempts_per_episode
        self.bot_threshold = bot_threshold

        self.state_builder = StateBuilder(feature_dim=state_dim)

        if reward_config:
            self.reward_fn = RewardFunction(**reward_config)
        else:
            self.reward_fn = RewardFunction()

        self.current_step = 0
        self.current_difficulty = 1
        self.attempt_count = 0
        self.total_human_correct = 0
        self.total_human_sessions = 0
        self.total_bot_correct = 0
        self.total_bot_sessions = 0
        self.done = False
        self.observation = None
        self.last_reward_breakdown = {}
        self.last_action = 0
        self.history = []

    def reset(
        self,
        mouse_events: list[dict] = None,
        keyboard_events: list[dict] = None,
        touch_events: list[dict] = None,
        scroll_events: list[dict] = None,
        bot_score: float = 0.0,
        confidence: float = 0.5,
    ) -> np.ndarray:
        self.current_step = 0
        self.current_difficulty = 1
        self.attempt_count = 0
        self.done = False
        self.last_reward_breakdown = {}
        self.last_action = 0

        self.observation = self.state_builder.build(
            mouse_events=mouse_events,
            keyboard_events=keyboard_events,
            touch_events=touch_events,
            scroll_events=scroll_events,
            previous_difficulty=self.current_difficulty,
            attempt_count=self.attempt_count,
            bot_score=bot_score,
            confidence=confidence,
        )

        return self.observation

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, dict]:
        if self.done:
            return self.observation, 0.0, True, {"reason": "episode_ended"}

        action = int(np.clip(action, 0, self.num_actions - 1))
        self.last_action = action
        difficulty = action_to_difficulty(action)
        self.current_difficulty = difficulty
        self.attempt_count += 1
        self.current_step += 1

        info = {
            "action": action,
            "action_name": action_name(action),
            "difficulty": difficulty,
            "attempt": self.attempt_count,
            "step": self.current_step,
        }

        if action == 0:
            info["decision"] = "allow"
            self.done = True
        elif action == 1:
            info["decision"] = "observe"
        elif action in (2, 3, 4):
            info["decision"] = "captcha"
        elif action == 5:
            info["decision"] = "honeypot"
        elif action == 6:
            info["decision"] = "block"
            self.done = True

        if self.current_step >= self.max_steps:
            self.done = True
            info["reason"] = "max_steps_reached"

        return self.observation, 0.0, self.done, info

    def receive_outcome(
        self,
        is_correct: bool,
        is_bot: bool,
        solve_time_ms: float = 0.0,
    ) -> float:
        reward, breakdown = self.reward_fn.compute(
            is_correct=is_correct,
            is_bot=is_bot,
            difficulty=self.current_difficulty,
            solve_time_ms=solve_time_ms,
            attempt_count=self.attempt_count,
            max_attempts=self.max_attempts_per_episode,
            action=self.last_action,
        )

        self.last_reward_breakdown = breakdown

        if is_bot:
            self.total_bot_sessions += 1
            if is_correct:
                self.total_bot_correct += 1
        else:
            self.total_human_sessions += 1
            if is_correct:
                self.total_human_correct += 1

        self.history.append({
            "step": self.current_step,
            "action": self.last_action,
            "action_name": action_name(self.last_action),
            "difficulty": self.current_difficulty,
            "is_correct": is_correct,
            "is_bot": is_bot,
            "reward": reward,
            "solve_time_ms": solve_time_ms,
            "breakdown": breakdown,
        })

        if self.attempt_count >= self.max_attempts_per_episode:
            self.done = True

        return reward

    def get_stats(self) -> dict:
        human_acc = (
            self.total_human_correct / max(self.total_human_sessions, 1)
        )
        bot_acc = (
            self.total_bot_correct / max(self.total_bot_sessions, 1)
        )

        recent_rewards = [h["reward"] for h in self.history[-20:]] if self.history else [0]

        return {
            "current_step": self.current_step,
            "current_difficulty": self.current_difficulty,
            "attempt_count": self.attempt_count,
            "done": self.done,
            "total_human_sessions": self.total_human_sessions,
            "total_bot_sessions": self.total_bot_sessions,
            "human_accuracy": round(human_acc, 4),
            "bot_accuracy": round(bot_acc, 4),
            "avg_recent_reward": round(float(np.mean(recent_rewards)), 4),
            "last_reward_breakdown": self.last_reward_breakdown,
        }

    def get_action_mask(self) -> list[bool]:
        return [True] * self.num_actions

    def set_difficulty(self, difficulty: int):
        self.current_difficulty = max(1, min(difficulty, 3))
