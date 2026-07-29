import os
import sys
import json
import numpy as np
import torch
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.ppo import PPOAgent
from agent.softppo import SoftPPOAgent
from agent.dg import DualGeneratorAgent
from environment.state import StateBuilder
from features.extractor import FeatureExtractor
from environment.security_actions import NUM_ACTIONS, SECURITY_ACTIONS, action_to_difficulty, action_name


class CaptchaPredictor:
    def __init__(
        self,
        agent_type: str = "ppo",
        model_path: str = None,
        state_dim: int = 20,
        action_dim: int = NUM_ACTIONS,
        hidden_dim: int = 128,
        lstm_dim: int = 64,
        device: str = "cpu",
    ):
        self.agent_type = agent_type
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = torch.device(device)

        self.state_builder = StateBuilder(feature_dim=state_dim)
        self.feature_extractor = FeatureExtractor()

        if agent_type == "ppo":
            self.agent = PPOAgent(
                obs_dim=state_dim,
                action_dim=action_dim,
                hidden_dim=hidden_dim,
                lstm_dim=lstm_dim,
                device=device,
            )
        elif agent_type == "softppo":
            self.agent = SoftPPOAgent(
                obs_dim=state_dim,
                action_dim=action_dim,
                hidden_dim=hidden_dim,
                lstm_dim=lstm_dim,
                device=device,
            )
        elif agent_type == "dg":
            self.agent = DualGeneratorAgent(
                obs_dim=state_dim,
                action_dim=action_dim,
                hidden_dim=hidden_dim,
                lstm_dim=lstm_dim,
                device=device,
            )
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

        if model_path and os.path.isfile(model_path):
            self.agent.load(model_path)
            self._loaded = True
        else:
            self._loaded = False

    def predict_action(
        self,
        mouse_events: list[dict] = None,
        keyboard_events: list[dict] = None,
        touch_events: list[dict] = None,
        scroll_events: list[dict] = None,
        previous_difficulty: int = 1,
        attempt_count: int = 0,
        session_duration_ms: float = 0.0,
        bot_score: float = 0.0,
        confidence: float = 0.5,
    ) -> dict:
        state = self.state_builder.build(
            mouse_events=mouse_events,
            keyboard_events=keyboard_events,
            touch_events=touch_events,
            scroll_events=scroll_events,
            previous_difficulty=previous_difficulty,
            attempt_count=attempt_count,
            session_duration_ms=session_duration_ms,
            bot_score=bot_score,
            confidence=confidence,
        )

        action, log_prob, value = self.agent.select_action(state, deterministic=True)
        action_int = int(np.clip(action, 0, self.action_dim - 1))

        return {
            "action": action_int,
            "action_name": action_name(action_int),
            "difficulty": action_to_difficulty(action_int),
            "decision": self._decision_summary(action_int),
            "raw_action": float(action),
            "log_prob": log_prob,
            "value": value,
            "state": state.tolist(),
        }

    def _decision_summary(self, action: int) -> dict:
        summaries = {
            0: {"type": "allow", "description": "Trusted session — skip CAPTCHA"},
            1: {"type": "observe", "description": "Collect more behavior data"},
            2: {"type": "captcha", "difficulty": 1, "description": "Easy CAPTCHA — 3 Bangla words"},
            3: {"type": "captcha", "difficulty": 2, "description": "Medium CAPTCHA — 4 Bangla words"},
            4: {"type": "captcha", "difficulty": 3, "description": "Hard CAPTCHA — 5 words, heavy distortion"},
            5: {"type": "honeypot", "description": "Fake CAPTCHA to trap bots"},
            6: {"type": "block", "description": "Session blocked — suspected bot"},
        }
        return summaries.get(action, {"type": "unknown"})

    def predict_difficulty(
        self,
        mouse_events: list[dict] = None,
        keyboard_events: list[dict] = None,
        touch_events: list[dict] = None,
        scroll_events: list[dict] = None,
        previous_difficulty: int = 1,
        attempt_count: int = 0,
        session_duration_ms: float = 0.0,
        bot_score: float = 0.0,
        confidence: float = 0.5,
    ) -> dict:
        return self.predict_action(
            mouse_events=mouse_events,
            keyboard_events=keyboard_events,
            touch_events=touch_events,
            scroll_events=scroll_events,
            previous_difficulty=previous_difficulty,
            attempt_count=attempt_count,
            session_duration_ms=session_duration_ms,
            bot_score=bot_score,
            confidence=confidence,
        )

    def predict_from_session(self, session: dict) -> dict:
        return self.predict_action(
            mouse_events=session.get("mouse_events", []),
            keyboard_events=session.get("keyboard_events", []),
            touch_events=session.get("touch_events", []),
            scroll_events=session.get("scroll_events", []),
            previous_difficulty=session.get("previous_difficulty", 1),
            attempt_count=session.get("attempt_count", 0),
            session_duration_ms=session.get("session_duration_ms", 0.0),
            bot_score=session.get("bot_score", 0.0),
            confidence=session.get("confidence", 0.5),
        )

    def predict_batch(self, sessions: list[dict]) -> list[dict]:
        return [self.predict_from_session(s) for s in sessions]

    def update(
        self,
        mouse_events: list[dict] = None,
        keyboard_events: list[dict] = None,
        touch_events: list[dict] = None,
        scroll_events: list[dict] = None,
        action: int = 2,
        reward: float = 0.0,
        done: bool = False,
        previous_difficulty: int = 1,
        attempt_count: int = 0,
        session_duration_ms: float = 0.0,
        bot_score: float = 0.0,
        confidence: float = 0.5,
    ) -> dict:
        state = self.state_builder.build(
            mouse_events=mouse_events,
            keyboard_events=keyboard_events,
            touch_events=touch_events,
            scroll_events=scroll_events,
            previous_difficulty=previous_difficulty,
            attempt_count=attempt_count,
            session_duration_ms=session_duration_ms,
            bot_score=bot_score,
            confidence=confidence,
        )

        action_val, log_prob, value = self.agent.select_action(state)
        self.agent.store_transition(state, action, log_prob, reward, done, value)

        if done:
            stats = self.agent.update()
            self.agent.reset_hidden()
            return stats

        return {}

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def save(self, path: str):
        self.agent.save(path)

    def load(self, path: str):
        self.agent.load(path)
        self._loaded = True

    def get_stats(self) -> dict:
        return self.agent.get_stats()


def get_predictor(
    agent_type: str = "ppo",
    model_path: str = None,
    checkpoints_dir: str = None,
) -> CaptchaPredictor:
    if checkpoints_dir is None:
        checkpoints_dir = os.path.join(os.path.dirname(__file__), "..", "checkpoints")

    if model_path is None:
        model_path = os.path.join(checkpoints_dir, f"{agent_type}_best.pt")

    predictor = CaptchaPredictor(
        agent_type=agent_type,
        model_path=model_path,
    )
    return predictor
