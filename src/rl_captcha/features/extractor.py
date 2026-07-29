import os
import sys
import math
import numpy as np
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from behavioral_biometrics import FeatureVectorizer, BehaviorProfile


class FeatureExtractor:
    def __init__(self):
        self.vectorizer = FeatureVectorizer()

    def extract(
        self,
        mouse_events: list[dict] = None,
        keyboard_events: list[dict] = None,
        touch_events: list[dict] = None,
        scroll_events: list[dict] = None,
    ) -> dict:
        profile = self.vectorizer.extract(
            mouse_events=mouse_events or [],
            keyboard_events=keyboard_events or [],
            touch_events=touch_events or [],
            scroll_events=scroll_events or [],
        )

        features = {}

        if profile.mouse:
            ms = profile.mouse
            features["mouse_avg_speed"] = ms.avg_speed
            features["mouse_std_speed"] = ms.std_speed
            features["mouse_max_speed"] = ms.max_speed
            features["mouse_path_length"] = ms.total_distance
            features["mouse_displacement"] = ms.total_displacement
            features["mouse_idle_periods"] = ms.idle_periods
            features["mouse_click_count"] = ms.total_clicks
            features["mouse_right_clicks"] = ms.total_right_clicks
            features["mouse_double_clicks"] = ms.double_click_count
            features["mouse_efficiency"] = ms.movement_efficiency
            features["mouse_curvature"] = ms.path_curvature
            features["mouse_direction_changes"] = ms.direction_changes
            features["mouse_jerkiness"] = ms.jerkiness
            features["mouse_x_range"] = ms.x_range
            features["mouse_y_range"] = ms.y_range
            features["mouse_entry_angle"] = ms.entry_angle
            features["mouse_pause_count"] = ms.pause_count

        if profile.keyboard:
            kb = profile.keyboard
            features["kb_total_keystrokes"] = kb.total_keystrokes
            features["kb_dwell_mean"] = kb.avg_dwell_time
            features["kb_dwell_std"] = kb.std_dwell_time
            features["kb_dwell_max"] = kb.max_dwell_time
            features["kb_dwell_min"] = kb.min_dwell_time
            features["kb_flight_mean"] = kb.avg_flight_time
            features["kb_flight_std"] = kb.std_flight_time
            features["kb_total_time_mean"] = kb.avg_total_time
            features["kb_speed_cpm"] = kb.typing_speed_cpm
            features["kb_speed_kpm"] = kb.typing_speed_kpm
            features["kb_rhythm"] = kb.rhythm_regularity
            features["kb_digraph_count"] = kb.num_digraphs
            features["kb_digraph_consistency"] = kb.digraph_consistency
            features["kb_correction_count"] = kb.correction_count
            features["kb_correction_ratio"] = kb.correction_ratio
            features["kb_paste_events"] = kb.paste_events
            features["kb_paste_chars"] = kb.paste_chars
            features["kb_pause_count"] = kb.pause_count
            features["kb_burst_count"] = kb.typing_bursts
            features["kb_burst_length"] = kb.avg_burst_length
            features["kb_flight_dwell_ratio"] = kb.flight_dwell_ratio
            features["kb_intensity_variation"] = kb.key_intensity_variation
            features["kb_error_rate"] = kb.error_rate

        if profile.touch:
            tp = profile.touch
            features["touch_count"] = tp.total_touches
            features["touch_taps"] = tp.total_taps
            features["touch_swipes"] = tp.total_swipes
            features["touch_long_presses"] = tp.total_long_presses
            features["touch_duration_mean"] = tp.avg_touch_duration
            features["touch_duration_std"] = tp.std_touch_duration
            features["touch_area_mean"] = tp.avg_touch_area
            features["touch_force_mean"] = tp.avg_force
            features["touch_force_std"] = tp.std_force
            features["touch_jitter"] = tp.jitter
            features["touch_speed_std"] = tp.touch_speed_std
            features["touch_swipe_speed"] = tp.avg_swipe_speed
            features["touch_tap_interval_mean"] = tp.avg_tap_interval
            features["touch_tap_accuracy"] = tp.tap_accuracy_std

        if profile.scroll:
            sc = profile.scroll
            features["scroll_events"] = sc.total_scroll_events
            features["scroll_distance_y"] = sc.total_scroll_distance_y
            features["scroll_distance_x"] = sc.total_scroll_distance_x
            features["scroll_speed"] = sc.avg_scroll_speed_y
            features["scroll_max_speed"] = sc.max_scroll_speed_y
            features["scroll_smoothness"] = sc.scroll_smoothness
            features["scroll_direction_changes"] = sc.scroll_direction_changes
            features["scroll_completion"] = sc.scroll_completion
            features["scroll_bursts"] = sc.scroll_bursts
            features["scroll_pause_count"] = sc.scroll_pause_count
            features["scroll_jerkiness"] = sc.scroll_jerkiness
            features["scroll_horizontal_bias"] = sc.horizontal_bias
            features["scroll_read_pct"] = sc.page_read_percentage

        features["feature_count"] = len(profile.feature_vector)
        features["feature_vector"] = profile.feature_vector

        return features

    def extract_for_rl(
        self,
        mouse_events: list[dict] = None,
        keyboard_events: list[dict] = None,
        touch_events: list[dict] = None,
        scroll_events: list[dict] = None,
        previous_difficulty: int = 1,
        attempt_count: int = 0,
        session_duration_ms: float = 0.0,
    ) -> np.ndarray:
        raw = self.extract(
            mouse_events=mouse_events,
            keyboard_events=keyboard_events,
            touch_events=touch_events,
            scroll_events=scroll_events,
        )

        feature_keys = [
            "mouse_avg_speed", "mouse_std_speed", "mouse_path_length",
            "mouse_idle_periods", "mouse_click_count", "mouse_efficiency",
            "kb_dwell_mean", "kb_dwell_std", "kb_flight_mean",
            "kb_speed_cpm", "kb_rhythm", "kb_correction_ratio",
            "touch_count", "touch_jitter", "touch_force_mean",
            "scroll_events", "scroll_speed", "scroll_smoothness",
            "mouse_curvature", "mouse_jerkiness",
        ]

        state = np.zeros(20, dtype=np.float32)
        for i, key in enumerate(feature_keys):
            state[i] = raw.get(key, 0.0)

        return state

    def to_profile(self, events: dict) -> BehaviorProfile:
        return self.vectorizer.extract(
            mouse_events=events.get("mouse_events", []),
            keyboard_events=events.get("keyboard_events", []),
            touch_events=events.get("touch_events", []),
            scroll_events=events.get("scroll_events", []),
        )
