import math
import numpy as np
from dataclasses import dataclass, asdict


@dataclass
class ScrollEvent:
    scroll_x: float
    scroll_y: float
    timestamp: float
    delta_x: float = 0.0
    delta_y: float = 0.0
    page_height: float = 0.0
    viewport_height: float = 0.0


@dataclass
class ScrollFeatures:
    total_scroll_events: int = 0
    total_scroll_distance_y: float = 0.0
    total_scroll_distance_x: float = 0.0
    avg_scroll_speed_y: float = 0.0
    avg_scroll_speed_x: float = 0.0
    max_scroll_speed_y: float = 0.0
    max_scroll_speed_x: float = 0.0
    std_scroll_speed_y: float = 0.0
    std_scroll_speed_x: float = 0.0
    scroll_direction_changes: int = 0
    scroll_direction_ratio: float = 0.0
    avg_scroll_distance_per_event: float = 0.0
    std_scroll_distance_per_event: float = 0.0
    scroll_duration: float = 0.0
    scroll_pause_count: int = 0
    avg_scroll_pause_duration: float = 0.0
    scroll_acceleration_avg: float = 0.0
    scroll_acceleration_std: float = 0.0
    scroll_jerkiness: float = 0.0
    scroll_to_bottom_ratio: float = 0.0
    scroll_completion: float = 0.0
    scroll_bursts: int = 0
    avg_burst_length: float = 0.0
    scroll_smoothness: float = 0.0
    horizontal_bias: float = 0.0
    page_read_percentage: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class ScrollFeatureExtractor:
    def __init__(
        self,
        pause_threshold_ms: float = 800.0,
        burst_gap_ms: float = 300.0,
        scroll_pause_ms: float = 500.0,
    ):
        self.pause_threshold_ms = pause_threshold_ms
        self.burst_gap_ms = burst_gap_ms
        self.scroll_pause_ms = scroll_pause_ms

    def extract(self, events: list[dict]) -> ScrollFeatures:
        valid_fields = {f.name for f in ScrollEvent.__dataclass_fields__.values()}
        scroll_events = []
        for e in events:
            if isinstance(e, dict):
                filtered = {k: v for k, v in e.items() if k in valid_fields}
                scroll_events.append(ScrollEvent(**filtered))
            else:
                scroll_events.append(e)
        if not scroll_events:
            return ScrollFeatures()

        features = ScrollFeatures()
        features.total_scroll_events = len(scroll_events)

        self._extract_distance_features(scroll_events, features)
        self._extract_speed_features(scroll_events, features)
        self._extract_direction_features(scroll_events, features)
        self._extract_pause_features(scroll_events, features)
        self._extract_acceleration_features(scroll_events, features)
        self._extract_pattern_features(scroll_events, features)
        self._extract_completion_features(scroll_events, features)

        return features

    def _extract_distance_features(self, events: list[ScrollEvent], features: ScrollFeatures):
        distances_y = []
        distances_x = []

        for i in range(1, len(events)):
            dy = abs(events[i].scroll_y - events[i - 1].scroll_y)
            dx = abs(events[i].scroll_x - events[i - 1].scroll_x)
            distances_y.append(dy)
            distances_x.append(dx)

        features.total_scroll_distance_y = sum(distances_y)
        features.total_scroll_distance_x = sum(distances_x)

        if distances_y:
            features.avg_scroll_distance_per_event = float(np.mean(distances_y))
            features.std_scroll_distance_per_event = float(np.std(distances_y)) if len(distances_y) > 1 else 0.0

        if events:
            features.scroll_duration = events[-1].timestamp - events[0].timestamp

        if features.total_scroll_distance_x > 0 and features.total_scroll_distance_y > 0:
            features.horizontal_bias = features.total_scroll_distance_x / (
                features.total_scroll_distance_x + features.total_scroll_distance_y
            )

    def _extract_speed_features(self, events: list[ScrollEvent], features: ScrollFeatures):
        speeds_y = []
        speeds_x = []

        for i in range(1, len(events)):
            dt = (events[i].timestamp - events[i - 1].timestamp) / 1000.0
            if dt > 0:
                dy = events[i].scroll_y - events[i - 1].scroll_y
                dx = events[i].scroll_x - events[i - 1].scroll_x
                speeds_y.append(abs(dy) / dt)
                speeds_x.append(abs(dx) / dt)

        if speeds_y:
            features.avg_scroll_speed_y = float(np.mean(speeds_y))
            features.max_scroll_speed_y = max(speeds_y)
            features.std_scroll_speed_y = float(np.std(speeds_y)) if len(speeds_y) > 1 else 0.0

        if speeds_x:
            features.avg_scroll_speed_x = float(np.mean(speeds_x))
            features.max_scroll_speed_x = max(speeds_x)
            features.std_scroll_speed_x = float(np.std(speeds_x)) if len(speeds_x) > 1 else 0.0

    def _extract_direction_features(self, events: list[ScrollEvent], features: ScrollFeatures):
        if len(events) < 3:
            return

        direction_changes = 0
        for i in range(2, len(events)):
            prev_dy = events[i - 1].scroll_y - events[i - 2].scroll_y
            curr_dy = events[i].scroll_y - events[i - 1].scroll_y

            if prev_dy * curr_dy < 0:
                direction_changes += 1

        features.scroll_direction_changes = direction_changes
        features.scroll_direction_ratio = direction_changes / max(len(events) - 2, 1)

    def _extract_pause_features(self, events: list[ScrollEvent], features: ScrollFeatures):
        pauses = []
        for i in range(1, len(events)):
            dt = events[i].timestamp - events[i - 1].timestamp
            if dt >= self.scroll_pause_ms:
                pauses.append(dt)

        features.scroll_pause_count = len(pauses)
        if pauses:
            features.avg_scroll_pause_duration = float(np.mean(pauses))

    def _extract_acceleration_features(self, events: list[ScrollEvent], features: ScrollFeatures):
        speeds = []
        for i in range(1, len(events)):
            dt = (events[i].timestamp - events[i - 1].timestamp) / 1000.0
            if dt > 0:
                dy = events[i].scroll_y - events[i - 1].scroll_y
                speeds.append(abs(dy) / dt)

        if len(speeds) < 3:
            return

        accelerations = [
            (speeds[i] - speeds[i - 1]) / max((events[i + 1].timestamp - events[i].timestamp) / 1000.0, 0.001)
            for i in range(1, len(speeds) - 1)
            if i + 1 < len(events)
        ]

        if accelerations:
            features.scroll_acceleration_avg = float(np.mean(accelerations))
            features.scroll_acceleration_std = float(np.std(accelerations)) if len(accelerations) > 1 else 0.0

        if len(speeds) >= 3:
            jerks = [abs(speeds[i] - speeds[i - 1]) for i in range(1, len(speeds))]
            features.scroll_jerkiness = float(np.mean(jerks)) if jerks else 0.0

    def _extract_pattern_features(self, events: list[ScrollEvent], features: ScrollFeatures):
        bursts = []
        current_burst = 1
        for i in range(1, len(events)):
            gap = events[i].timestamp - events[i - 1].timestamp
            if gap < self.burst_gap_ms:
                current_burst += 1
            else:
                bursts.append(current_burst)
                current_burst = 1
        bursts.append(current_burst)

        features.scroll_bursts = len(bursts)
        features.avg_burst_length = float(np.mean(bursts)) if bursts else 0.0

        if len(events) >= 2:
            total_dy = [events[i].scroll_y - events[i - 1].scroll_y for i in range(1, len(events))]
            if total_dy:
                mean_dy = np.mean(total_dy)
                std_dy = np.std(total_dy)
                features.scroll_smoothness = float(std_dy / mean_dy) if abs(mean_dy) > 0 else 0.0

    def _extract_completion_features(self, events: list[ScrollEvent], features: ScrollFeatures):
        if not events:
            return

        has_page_info = any(e.page_height > 0 for e in events)
        if not has_page_info:
            return

        page_height = max(e.page_height for e in events if e.page_height > 0)
        viewport_height = max(e.viewport_height for e in events if e.viewport_height > 0)

        if page_height <= 0:
            return

        max_scroll_y = max(e.scroll_y for e in events)
        features.scroll_completion = min(max_scroll_y / max(page_height - viewport_height, 1), 1.0)

        min_scroll_y = min(e.scroll_y for e in events)
        total_viewed = max_scroll_y - min_scroll_y + viewport_height
        features.page_read_percentage = min(total_viewed / page_height, 1.0)

        if page_height > 0:
            scrollable_distance = page_height - viewport_height
            if scrollable_distance > 0:
                bottom_events = sum(
                    1 for e in events
                    if e.scroll_y >= scrollable_distance * 0.9
                )
                features.scroll_to_bottom_ratio = bottom_events / len(events)

    def to_dict(self, features: ScrollFeatures) -> dict:
        return {
            "total_scroll_events": features.total_scroll_events,
            "total_scroll_distance_y": round(features.total_scroll_distance_y, 2),
            "total_scroll_distance_x": round(features.total_scroll_distance_x, 2),
            "avg_scroll_speed_y": round(features.avg_scroll_speed_y, 2),
            "avg_scroll_speed_x": round(features.avg_scroll_speed_x, 2),
            "max_scroll_speed_y": round(features.max_scroll_speed_y, 2),
            "max_scroll_speed_x": round(features.max_scroll_speed_x, 2),
            "std_scroll_speed_y": round(features.std_scroll_speed_y, 2),
            "std_scroll_speed_x": round(features.std_scroll_speed_x, 2),
            "scroll_direction_changes": features.scroll_direction_changes,
            "scroll_direction_ratio": round(features.scroll_direction_ratio, 4),
            "avg_scroll_distance_per_event": round(features.avg_scroll_distance_per_event, 2),
            "std_scroll_distance_per_event": round(features.std_scroll_distance_per_event, 2),
            "scroll_duration": round(features.scroll_duration, 2),
            "scroll_pause_count": features.scroll_pause_count,
            "avg_scroll_pause_duration": round(features.avg_scroll_pause_duration, 2),
            "scroll_acceleration_avg": round(features.scroll_acceleration_avg, 2),
            "scroll_acceleration_std": round(features.scroll_acceleration_std, 2),
            "scroll_jerkiness": round(features.scroll_jerkiness, 2),
            "scroll_to_bottom_ratio": round(features.scroll_to_bottom_ratio, 4),
            "scroll_completion": round(features.scroll_completion, 4),
            "scroll_bursts": features.scroll_bursts,
            "avg_burst_length": round(features.avg_burst_length, 2),
            "scroll_smoothness": round(features.scroll_smoothness, 4),
            "horizontal_bias": round(features.horizontal_bias, 4),
            "page_read_percentage": round(features.page_read_percentage, 4),
        }
