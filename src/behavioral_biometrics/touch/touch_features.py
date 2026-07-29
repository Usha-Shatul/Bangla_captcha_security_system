import math
import numpy as np
from dataclasses import dataclass, asdict


@dataclass
class TouchPoint:
    x: float
    y: float
    timestamp: float
    touch_type: str = ""
    radius_x: float = 0.0
    radius_y: float = 0.0
    force: float = 0.0
    angle: float = 0.0


@dataclass
class TouchFeatures:
    total_touches: int = 0
    total_taps: int = 0
    total_swipes: int = 0
    total_long_presses: int = 0
    avg_touch_duration: float = 0.0
    std_touch_duration: float = 0.0
    max_touch_duration: float = 0.0
    avg_touch_area: float = 0.0
    std_touch_area: float = 0.0
    avg_force: float = 0.0
    std_force: float = 0.0
    max_force: float = 0.0
    avg_swipe_distance: float = 0.0
    avg_swipe_speed: float = 0.0
    max_swipe_speed: float = 0.0
    swipe_angle_std: float = 0.0
    avg_tap_interval: float = 0.0
    std_tap_interval: float = 0.0
    tap_accuracy_std: float = 0.0
    avg_pressure_variation: float = 0.0
    touch_speed_std: float = 0.0
    multi_touch_events: int = 0
    pinch_count: int = 0
    avg_pinch_distance: float = 0.0
    dwell_points: int = 0
    jitter: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class TouchFeatureExtractor:
    def __init__(
        self,
        long_press_threshold_ms: float = 500.0,
        swipe_min_distance: float = 50.0,
        tap_max_duration_ms: float = 300.0,
        tap_max_distance: float = 20.0,
        jitter_window: int = 5,
    ):
        self.long_press_threshold_ms = long_press_threshold_ms
        self.swipe_min_distance = swipe_min_distance
        self.tap_max_duration_ms = tap_max_duration_ms
        self.tap_max_distance = tap_max_distance
        self.jitter_window = jitter_window

    def extract(self, events: list[dict]) -> TouchFeatures:
        valid_fields = {f.name for f in TouchPoint.__dataclass_fields__.values()}
        points = []
        for e in events:
            if isinstance(e, dict):
                filtered = {k: v for k, v in e.items() if k in valid_fields}
                points.append(TouchPoint(**filtered))
            else:
                points.append(e)
        if not points:
            return TouchFeatures()

        features = TouchFeatures()
        gestures = self._segment_gestures(points)

        features.total_touches = len(points)
        features.total_taps = sum(1 for g in gestures if g["type"] == "tap")
        features.total_swipes = sum(1 for g in gestures if g["type"] == "swipe")
        features.total_long_presses = sum(1 for g in gestures if g["type"] == "long_press")

        self._extract_duration_features(points, features)
        self._extract_force_features(points, features)
        self._extract_swipe_features([g for g in gestures if g["type"] == "swipe"], features)
        self._extract_tap_features([g for g in gestures if g["type"] == "tap"], features)
        self._extract_area_features(points, features)
        self._extract_jitter(points, features)

        return features

    def _segment_gestures(self, points: list[TouchPoint]) -> list[dict]:
        if not points:
            return []

        gestures = []
        current_start = points[0]
        current_points = [points[0]]

        for i in range(1, len(points)):
            dt = points[i].timestamp - current_start.timestamp
            dx = points[i].x - current_points[0].x
            dy = points[i].y - current_points[0].y
            dist = math.sqrt(dx * dx + dy * dy)

            if points[i].touch_type in ("touchend", "end"):
                duration = points[i].timestamp - current_start.timestamp
                final_dist = math.sqrt(
                    (points[i].x - current_points[0].x) ** 2 +
                    (points[i].y - current_points[0].y) ** 2
                )

                if final_dist < self.tap_max_distance and duration < self.tap_max_duration_ms:
                    gestures.append({"type": "tap", "points": current_points, "duration": duration})
                elif duration >= self.long_press_threshold_ms and final_dist < self.tap_max_distance:
                    gestures.append({"type": "long_press", "points": current_points, "duration": duration})
                elif final_dist >= self.swipe_min_distance:
                    gestures.append({"type": "swipe", "points": current_points, "duration": duration})
                else:
                    gestures.append({"type": "tap", "points": current_points, "duration": duration})

                current_points = []
            else:
                current_points.append(points[i])
                if len(current_points) == 1:
                    current_start = points[i]

        return gestures

    def _extract_duration_features(self, points: list[TouchPoint], features: TouchFeatures):
        durations = []
        for i in range(1, len(points)):
            dt = points[i].timestamp - points[i - 1].timestamp
            durations.append(dt)

        if durations:
            features.avg_touch_duration = float(np.mean(durations))
            features.std_touch_duration = float(np.std(durations)) if len(durations) > 1 else 0.0
            features.max_touch_duration = max(durations)

    def _extract_force_features(self, points: list[TouchPoint], features: TouchFeatures):
        forces = [p.force for p in points if p.force > 0]
        if forces:
            features.avg_force = float(np.mean(forces))
            features.std_force = float(np.std(forces)) if len(forces) > 1 else 0.0
            features.max_force = max(forces)

            if len(forces) > 1:
                diffs = [abs(forces[i] - forces[i - 1]) for i in range(1, len(forces))]
                features.avg_pressure_variation = float(np.mean(diffs))

    def _extract_swipe_features(self, swipes: list[dict], features: TouchFeatures):
        if not swipes:
            return

        distances = []
        speeds = []
        angles = []

        for swipe in swipes:
            pts = swipe["points"]
            if len(pts) < 2:
                continue

            dx = pts[-1].x - pts[0].x
            dy = pts[-1].y - pts[0].y
            dist = math.sqrt(dx * dx + dy * dy)
            distances.append(dist)

            dt = (pts[-1].timestamp - pts[0].timestamp) / 1000.0
            if dt > 0:
                speeds.append(dist / dt)

            angles.append(math.atan2(dy, dx))

        if distances:
            features.avg_swipe_distance = float(np.mean(distances))
        if speeds:
            features.avg_swipe_speed = float(np.mean(speeds))
            features.max_swipe_speed = max(speeds)
        if len(angles) > 1:
            features.swipe_angle_std = float(np.std(angles))

    def _extract_tap_features(self, taps: list[dict], features: TouchFeatures):
        if not taps:
            return

        intervals = []
        for i in range(1, len(taps)):
            interval = taps[i]["points"][0].timestamp - taps[i - 1]["points"][0].timestamp
            intervals.append(interval)

        if intervals:
            features.avg_tap_interval = float(np.mean(intervals))
            features.std_tap_interval = float(np.std(intervals)) if len(intervals) > 1 else 0.0

        if len(taps) >= 2:
            tap_centers = [(t["points"][0].x, t["points"][0].y) for t in taps]
            if tap_centers:
                cx = np.mean([c[0] for c in tap_centers])
                cy = np.mean([c[1] for c in tap_centers])
                dists = [math.sqrt((c[0] - cx) ** 2 + (c[1] - cy) ** 2) for c in tap_centers]
                features.tap_accuracy_std = float(np.std(dists)) if len(dists) > 1 else 0.0

    def _extract_area_features(self, points: list[TouchPoint], features: TouchFeatures):
        areas = [
            math.pi * p.radius_x * p.radius_y
            for p in points
            if p.radius_x > 0 and p.radius_y > 0
        ]

        if areas:
            features.avg_touch_area = float(np.mean(areas))
            features.std_touch_area = float(np.std(areas)) if len(areas) > 1 else 0.0

    def _extract_jitter(self, points: list[TouchPoint], features: TouchFeatures):
        if len(points) < self.jitter_window:
            return

        x_coords = [p.x for p in points]
        y_coords = [p.y for p in points]

        x_diffs = [abs(x_coords[i] - x_coords[i - 1]) for i in range(1, len(x_coords))]
        y_diffs = [abs(y_coords[i] - y_coords[i - 1]) for i in range(1, len(y_coords))]

        if x_diffs and y_diffs:
            features.jitter = float(np.mean(x_diffs) + np.mean(y_diffs)) / 2.0

        speeds = []
        for i in range(1, len(points)):
            dx = points[i].x - points[i - 1].x
            dy = points[i].y - points[i - 1].y
            dt = points[i].timestamp - points[i - 1].timestamp
            if dt > 0:
                speeds.append(math.sqrt(dx * dx + dy * dy) / (dt / 1000.0))

        if len(speeds) > 1:
            features.touch_speed_std = float(np.std(speeds))

    def to_dict(self, features: TouchFeatures) -> dict:
        return {
            "total_touches": features.total_touches,
            "total_taps": features.total_taps,
            "total_swipes": features.total_swipes,
            "total_long_presses": features.total_long_presses,
            "avg_touch_duration": round(features.avg_touch_duration, 2),
            "std_touch_duration": round(features.std_touch_duration, 2),
            "max_touch_duration": round(features.max_touch_duration, 2),
            "avg_touch_area": round(features.avg_touch_area, 2),
            "std_touch_area": round(features.std_touch_area, 2),
            "avg_force": round(features.avg_force, 4),
            "std_force": round(features.std_force, 4),
            "max_force": round(features.max_force, 4),
            "avg_swipe_distance": round(features.avg_swipe_distance, 2),
            "avg_swipe_speed": round(features.avg_swipe_speed, 2),
            "max_swipe_speed": round(features.max_swipe_speed, 2),
            "swipe_angle_std": round(features.swipe_angle_std, 4),
            "avg_tap_interval": round(features.avg_tap_interval, 2),
            "std_tap_interval": round(features.std_tap_interval, 2),
            "tap_accuracy_std": round(features.tap_accuracy_std, 2),
            "avg_pressure_variation": round(features.avg_pressure_variation, 4),
            "touch_speed_std": round(features.touch_speed_std, 2),
            "multi_touch_events": features.multi_touch_events,
            "pinch_count": features.pinch_count,
            "avg_pinch_distance": round(features.avg_pinch_distance, 2),
            "dwell_points": features.dwell_points,
            "jitter": round(features.jitter, 4),
        }
