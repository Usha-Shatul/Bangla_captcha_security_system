import json
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from .mouse.mouse_features import MouseFeatureExtractor, MouseFeatures
from .keyboard.typing_features import TypingFeatureExtractor, TypingFeatures
from .touch.touch_features import TouchFeatureExtractor, TouchFeatures
from .scroll.scroll_features import ScrollFeatureExtractor, ScrollFeatures


MOUSE_FEATURE_NAMES = [
    "total_distance", "total_displacement", "avg_speed", "max_speed", "min_speed",
    "std_speed", "avg_acceleration", "max_acceleration", "std_acceleration",
    "total_clicks", "total_right_clicks", "double_click_count",
    "avg_click_interval", "std_click_interval", "avg_double_click_interval",
    "idle_periods", "avg_idle_duration", "longest_idle",
    "path_curvature", "direction_changes", "direction_change_ratio",
    "x_range", "y_range", "x_std", "y_std",
    "entry_angle", "movement_efficiency", "jerkiness", "pause_count",
]

KEYBOARD_FEATURE_NAMES = [
    "total_keystrokes", "total_keys_held",
    "avg_dwell_time", "std_dwell_time", "max_dwell_time", "min_dwell_time", "median_dwell_time",
    "avg_flight_time", "std_flight_time", "max_flight_time", "min_flight_time", "median_flight_time",
    "avg_total_time", "std_total_time",
    "typing_speed_cpm", "typing_speed_kpm", "avg_speed_std", "rhythm_regularity",
    "num_digraphs", "unique_digraphs",
    "avg_digraph_flight", "std_digraph_flight", "avg_digraph_dwell",
    "correction_count", "correction_ratio",
    "paste_events", "paste_chars", "delete_presses", "backspace_ratio", "modifier_usage_ratio",
    "pause_count", "avg_pause_duration", "longest_pause",
    "typing_bursts", "avg_burst_length", "key_intensity_variation",
    "error_rate", "digraph_consistency", "flight_dwell_ratio",
]

TOUCH_FEATURE_NAMES = [
    "total_touches", "total_taps", "total_swipes", "total_long_presses",
    "avg_touch_duration", "std_touch_duration", "max_touch_duration",
    "avg_touch_area", "std_touch_area",
    "avg_force", "std_force", "max_force",
    "avg_swipe_distance", "avg_swipe_speed", "max_swipe_speed", "swipe_angle_std",
    "avg_tap_interval", "std_tap_interval", "tap_accuracy_std",
    "avg_pressure_variation", "touch_speed_std",
    "multi_touch_events", "pinch_count", "avg_pinch_distance",
    "dwell_points", "jitter",
]

SCROLL_FEATURE_NAMES = [
    "total_scroll_events", "total_scroll_distance_y", "total_scroll_distance_x",
    "avg_scroll_speed_y", "avg_scroll_speed_x",
    "max_scroll_speed_y", "max_scroll_speed_x",
    "std_scroll_speed_y", "std_scroll_speed_x",
    "scroll_direction_changes", "scroll_direction_ratio",
    "avg_scroll_distance_per_event", "std_scroll_distance_per_event",
    "scroll_duration", "scroll_pause_count", "avg_scroll_pause_duration",
    "scroll_acceleration_avg", "scroll_acceleration_std", "scroll_jerkiness",
    "scroll_to_bottom_ratio", "scroll_completion",
    "scroll_bursts", "avg_burst_length", "scroll_smoothness",
    "horizontal_bias", "page_read_percentage",
]


ALL_FEATURE_NAMES = (
    ["mod_mouse_" + f for f in MOUSE_FEATURE_NAMES]
    + ["mod_keyboard_" + f for f in KEYBOARD_FEATURE_NAMES]
    + ["mod_touch_" + f for f in TOUCH_FEATURE_NAMES]
    + ["mod_scroll_" + f for f in SCROLL_FEATURE_NAMES]
)

MOUSE_INDICES = list(range(len(MOUSE_FEATURE_NAMES)))
KEYBOARD_INDICES = list(range(len(MOUSE_FEATURE_NAMES), len(MOUSE_FEATURE_NAMES) + len(KEYBOARD_FEATURE_NAMES)))
TOUCH_INDICES = list(range(
    len(MOUSE_FEATURE_NAMES) + len(KEYBOARD_FEATURE_NAMES),
    len(MOUSE_FEATURE_NAMES) + len(KEYBOARD_FEATURE_NAMES) + len(TOUCH_FEATURE_NAMES),
))
SCROLL_INDICES = list(range(
    len(MOUSE_FEATURE_NAMES) + len(KEYBOARD_FEATURE_NAMES) + len(TOUCH_FEATURE_NAMES),
    len(ALL_FEATURE_NAMES),
))


@dataclass
class BehaviorProfile:
    mouse: Optional[MouseFeatures] = None
    keyboard: Optional[TypingFeatures] = None
    touch: Optional[TouchFeatures] = None
    scroll: Optional[ScrollFeatures] = None
    feature_vector: list[float] = field(default_factory=list)
    feature_names: list[str] = field(default_factory=list)
    bot_score: float = 0.0
    is_bot: bool = False
    raw_events: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = {
            "bot_score": round(self.bot_score, 4),
            "is_bot": self.is_bot,
            "feature_count": len(self.feature_vector),
        }
        if self.mouse:
            result["mouse"] = self.mouse.to_dict()
        if self.keyboard:
            result["keyboard"] = self.keyboard.to_dict()
        if self.touch:
            result["touch"] = self.touch.to_dict()
        if self.scroll:
            result["scroll"] = self.scroll.to_dict()
        return result


class FeatureVectorizer:
    def __init__(
        self,
        mouse_idle_threshold_ms: float = 1000.0,
        keyboard_pause_threshold_ms: float = 2000.0,
        touch_long_press_ms: float = 500.0,
        scroll_pause_ms: float = 800.0,
    ):
        self.mouse_extractor = MouseFeatureExtractor(idle_threshold_ms=mouse_idle_threshold_ms)
        self.keyboard_extractor = TypingFeatureExtractor(pause_threshold_ms=keyboard_pause_threshold_ms)
        self.touch_extractor = TouchFeatureExtractor(long_press_threshold_ms=touch_long_press_ms)
        self.scroll_extractor = ScrollFeatureExtractor(pause_threshold_ms=scroll_pause_ms)

        self.feature_names = ALL_FEATURE_NAMES

    def extract(
        self,
        mouse_events: list[dict] = None,
        keyboard_events: list[dict] = None,
        touch_events: list[dict] = None,
        scroll_events: list[dict] = None,
    ) -> BehaviorProfile:
        profile = BehaviorProfile()
        profile.raw_events = {
            "mouse": mouse_events or [],
            "keyboard": keyboard_events or [],
            "touch": touch_events or [],
            "scroll": scroll_events or [],
        }

        vector = []
        names = []

        mouse_feat = self.mouse_extractor.extract(mouse_events or [])
        profile.mouse = mouse_feat
        mouse_dict = self.mouse_extractor.to_dict(mouse_feat)
        for name in MOUSE_FEATURE_NAMES:
            vector.append(mouse_dict.get(name, 0.0))
            names.append("mod_mouse_" + name)

        kb_feat = self.keyboard_extractor.extract(keyboard_events or [])
        profile.keyboard = kb_feat
        kb_dict = self.keyboard_extractor.to_dict(kb_feat)
        for name in KEYBOARD_FEATURE_NAMES:
            vector.append(kb_dict.get(name, 0.0))
            names.append("mod_keyboard_" + name)

        touch_feat = self.touch_extractor.extract(touch_events or [])
        profile.touch = touch_feat
        touch_dict = self.touch_extractor.to_dict(touch_feat)
        for name in TOUCH_FEATURE_NAMES:
            vector.append(touch_dict.get(name, 0.0))
            names.append("mod_touch_" + name)

        scroll_feat = self.scroll_extractor.extract(scroll_events or [])
        profile.scroll = scroll_feat
        scroll_dict = self.scroll_extractor.to_dict(scroll_feat)
        for name in SCROLL_FEATURE_NAMES:
            vector.append(scroll_dict.get(name, 0.0))
            names.append("mod_scroll_" + name)

        profile.feature_vector = vector
        profile.feature_names = names

        return profile

    def extract_numpy(self, **kwargs) -> np.ndarray:
        profile = self.extract(**kwargs)
        return np.array(profile.feature_vector, dtype=np.float32)

    def vector_to_numpy(self, profile: BehaviorProfile) -> np.ndarray:
        return np.array(profile.feature_vector, dtype=np.float32)

    def normalize(self, vector: np.ndarray, mean: np.ndarray = None, std: np.ndarray = None) -> np.ndarray:
        if mean is None:
            mean = np.zeros(len(vector))
        if std is None:
            std = np.ones(len(vector))
        std = np.where(std == 0, 1.0, std)
        return (vector - mean) / std

    def get_feature_indices(self, modality: str) -> list[int]:
        if modality == "mouse":
            return MOUSE_INDICES
        elif modality == "keyboard":
            return KEYBOARD_INDICES
        elif modality == "touch":
            return TOUCH_INDICES
        elif modality == "scroll":
            return SCROLL_INDICES
        return []

    def profile_to_json(self, profile: BehaviorProfile) -> str:
        return json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)


def compute_bot_score_heuristic(profile: BehaviorProfile) -> float:
    score = 0.0
    total_weight = 0.0

    if profile.keyboard and profile.keyboard.total_keystrokes > 0:
        kb = profile.keyboard
        if kb.paste_events > 0:
            score += 0.25
        total_weight += 0.25

        if kb.std_dwell_time < 5 and kb.total_keystrokes > 5:
            score += 0.15
        total_weight += 0.15

        if kb.typing_speed_cpm > 300:
            score += 0.10
        total_weight += 0.10

        if kb.correction_ratio < 0.01 and kb.total_keystrokes > 20:
            score += 0.10
        total_weight += 0.10

        if kb.rhythm_regularity < 0.1:
            score += 0.05
        total_weight += 0.05

    if profile.mouse and profile.mouse.total_distance > 0:
        ms = profile.mouse

        if ms.avg_speed > 5000:
            score += 0.10
        total_weight += 0.10

        if ms.std_speed < 10 and ms.total_distance > 100:
            score += 0.10
        total_weight += 0.10

        if ms.idle_periods == 0 and ms.total_distance > 500:
            score += 0.05
        total_weight += 0.05

        if ms.movement_efficiency > 0.95 and ms.total_distance > 200:
            score += 0.05
        total_weight += 0.05

    if profile.touch and profile.touch.total_touches > 0:
        tp = profile.touch
        if tp.jitter < 0.5 and tp.total_touches > 3:
            score += 0.10
        total_weight += 0.10

    if total_weight > 0:
        score = score / total_weight

    return min(max(score, 0.0), 1.0)
