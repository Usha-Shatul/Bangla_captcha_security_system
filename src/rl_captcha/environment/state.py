import os
import sys
import numpy as np
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from features.extractor import FeatureExtractor


class StateBuilder:
    def __init__(self, feature_dim: int = 20):
        self.feature_dim = feature_dim
        self.extractor = FeatureExtractor()
        self.num_actions = 7
        self.action_dim = self.num_actions

    def build(
        self,
        mouse_events: list[dict] = None,
        keyboard_events: list[dict] = None,
        touch_events: list[dict] = None,
        scroll_events: list[dict] = None,
        captcha_text: str = "",
        previous_difficulty: int = 1,
        attempt_count: int = 0,
        session_duration_ms: float = 0.0,
        bot_score: float = 0.0,
        confidence: float = 0.5,
    ) -> np.ndarray:
        features = self.extractor.extract(
            mouse_events=mouse_events,
            keyboard_events=keyboard_events,
            touch_events=touch_events,
            scroll_events=scroll_events,
        )

        state = np.zeros(self.feature_dim, dtype=np.float32)

        feature_keys = [
            "mouse_avg_speed", "mouse_std_speed", "mouse_path_length",
            "mouse_idle_periods", "mouse_click_count", "mouse_efficiency",
            "kb_dwell_mean", "kb_dwell_std", "kb_flight_mean",
            "kb_speed_cpm", "kb_rhythm", "kb_correction_ratio",
            "touch_count", "touch_jitter", "touch_force_mean",
            "scroll_events", "scroll_speed", "scroll_smoothness",
            "bot_score", "confidence",
        ]

        for i, key in enumerate(feature_keys[:self.feature_dim]):
            if key == "bot_score":
                state[i] = bot_score
            elif key == "confidence":
                state[i] = confidence
            elif key in features:
                state[i] = features[key]

        meta_idx = self.feature_dim - 3
        state[meta_idx] = previous_difficulty / 3.0
        state[meta_idx + 1] = attempt_count / 3.0
        state[meta_idx + 2] = min(session_duration_ms / 30000.0, 1.0)

        return state

    def get_state_dim(self) -> int:
        return self.feature_dim

    def get_action_dim(self) -> int:
        return self.num_actions

    def normalize(self, state: np.ndarray, mean: np.ndarray = None, std: np.ndarray = None) -> np.ndarray:
        if mean is None:
            mean = np.zeros(self.feature_dim)
        if std is None:
            std = np.ones(self.feature_dim)
        std = np.where(std == 0, 1.0, std)
        return (state - mean) / std
