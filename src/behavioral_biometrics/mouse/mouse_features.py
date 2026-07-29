import math
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class MousePoint:
    x: float = 0.0
    y: float = 0.0
    timestamp: float = 0.0
    button: int = 0
    click_type: str = ""
    pressure: float = 0.0


@dataclass
class MouseFeatures:
    total_distance: float = 0.0
    total_displacement: float = 0.0
    avg_speed: float = 0.0
    max_speed: float = 0.0
    min_speed: float = 0.0
    std_speed: float = 0.0
    avg_acceleration: float = 0.0
    max_acceleration: float = 0.0
    std_acceleration: float = 0.0
    total_clicks: int = 0
    total_right_clicks: int = 0
    double_click_count: int = 0
    avg_click_interval: float = 0.0
    std_click_interval: float = 0.0
    avg_double_click_interval: float = 0.0
    idle_periods: int = 0
    avg_idle_duration: float = 0.0
    longest_idle: float = 0.0
    path_curvature: float = 0.0
    direction_changes: int = 0
    direction_change_ratio: float = 0.0
    x_range: float = 0.0
    y_range: float = 0.0
    x_std: float = 0.0
    y_std: float = 0.0
    entry_angle: float = 0.0
    movement_efficiency: float = 0.0
    jerkiness: float = 0.0
    pause_count: int = 0
    to_target_angle_std: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class MouseFeatureExtractor:
    def __init__(
        self,
        idle_threshold_ms: float = 1000.0,
        pause_threshold_ms: float = 500.0,
        click_window_ms: float = 400.0,
        pixel_scale: float = 1.0,
    ):
        self.idle_threshold_ms = idle_threshold_ms
        self.pause_threshold_ms = pause_threshold_ms
        self.click_window_ms = click_window_ms
        self.pixel_scale = pixel_scale

    def extract(self, events: list[dict]) -> MouseFeatures:
        valid_fields = {f.name for f in MousePoint.__dataclass_fields__.values()}
        points = []
        for e in events:
            if isinstance(e, dict):
                filtered = {k: v for k, v in e.items() if k in valid_fields}
                if "timestamp" not in filtered:
                    filtered["timestamp"] = 0.0
                filtered.setdefault("x", 0.0)
                filtered.setdefault("y", 0.0)
                points.append(MousePoint(**filtered))
            elif isinstance(e, MousePoint):
                points.append(e)
        if len(points) < 2:
            return MouseFeatures()

        features = MouseFeatures()

        moves = [p for p in points if p.click_type == ""]
        clicks = [p for p in points if p.click_type in ("click", "dblclick", "rightclick")]

        if len(moves) >= 2:
            self._extract_movement_features(moves, features)

        if clicks:
            self._extract_click_features(clicks, features)

        self._extract_spatial_features(moves, features)
        self._extract_idle_features(moves, features)
        self._extract_path_features(moves, features)

        return features

    def _extract_movement_features(self, points: list[MousePoint], features: MouseFeatures):
        distances = []
        speeds = []
        accelerations = []
        intervals = []

        for i in range(1, len(points)):
            dx = (points[i].x - points[i - 1].x) * self.pixel_scale
            dy = (points[i].y - points[i - 1].y) * self.pixel_scale
            dt = points[i].timestamp - points[i - 1].timestamp

            dist = math.sqrt(dx * dx + dy * dy)
            distances.append(dist)

            if dt > 0:
                speed = dist / (dt / 1000.0)
                speeds.append(speed)
                intervals.append(dt)

        for i in range(1, len(speeds)):
            dt = intervals[i] / 1000.0 if i < len(intervals) else 0.01
            if dt > 0:
                acc = (speeds[i] - speeds[i - 1]) / dt
                accelerations.append(acc)

        features.total_distance = sum(distances)

        dx_total = (points[-1].x - points[0].x) * self.pixel_scale
        dy_total = (points[-1].y - points[0].y) * self.pixel_scale
        features.total_displacement = math.sqrt(dx_total * dx_total + dy_total * dy_total)

        if speeds:
            features.avg_speed = float(np.mean(speeds))
            features.max_speed = float(np.max(speeds))
            features.min_speed = float(np.min(speeds))
            features.std_speed = float(np.std(speeds)) if len(speeds) > 1 else 0.0

        if accelerations:
            features.avg_acceleration = float(np.mean(accelerations))
            features.max_acceleration = float(np.max(np.abs(accelerations)))
            features.std_acceleration = float(np.std(accelerations)) if len(accelerations) > 1 else 0.0

        features.avg_click_interval = 0.0
        features.std_click_interval = 0.0

    def _extract_click_features(self, clicks: list[MousePoint], features: MouseFeatures):
        features.total_clicks = len(clicks)
        features.total_right_clicks = sum(1 for c in clicks if c.button == 2)

        click_times = sorted(c.timestamp for c in clicks)
        if len(click_times) > 1:
            intervals = [click_times[i] - click_times[i - 1] for i in range(1, len(click_times))]
            features.avg_click_interval = float(np.mean(intervals))
            features.std_click_interval = float(np.std(intervals)) if len(intervals) > 1 else 0.0

        double_intervals = []
        i = 0
        while i < len(click_times) - 1:
            if click_times[i + 1] - click_times[i] <= self.click_window_ms:
                double_intervals.append(click_times[i + 1] - click_times[i])
                features.double_click_count += 1
                i += 2
            else:
                i += 1

        if double_intervals:
            features.avg_double_click_interval = float(np.mean(double_intervals))

    def _extract_spatial_features(self, points: list[MousePoint], features: MouseFeatures):
        xs = [p.x for p in points]
        ys = [p.y for p in points]

        features.x_range = max(xs) - min(xs)
        features.y_range = max(ys) - min(ys)
        features.x_std = float(np.std(xs)) if len(xs) > 1 else 0.0
        features.y_std = float(np.std(ys)) if len(ys) > 1 else 0.0

    def _extract_idle_features(self, points: list[MousePoint], features: MouseFeatures):
        idle_durations = []
        for i in range(1, len(points)):
            dt = points[i].timestamp - points[i - 1].timestamp
            if dt >= self.idle_threshold_ms:
                idle_durations.append(dt)

        features.idle_periods = len(idle_durations)
        if idle_durations:
            features.avg_idle_duration = float(np.mean(idle_durations))
            features.longest_idle = max(idle_durations)

    def _extract_path_features(self, points: list[MousePoint], features: MouseFeatures):
        if len(points) < 3:
            return

        direction_changes = 0
        angles = []

        for i in range(2, len(points)):
            dx1 = points[i - 1].x - points[i - 2].x
            dy1 = points[i - 1].y - points[i - 2].y
            dx2 = points[i].x - points[i - 1].x
            dy2 = points[i].y - points[i - 1].y

            angle1 = math.atan2(dy1, dx1)
            angle2 = math.atan2(dy2, dx2)
            angles.append(angle2)

            diff = abs(angle2 - angle1)
            if diff > math.pi:
                diff = 2 * math.pi - diff

            if diff > math.pi / 4:
                direction_changes += 1

        features.direction_changes = direction_changes
        features.direction_change_ratio = direction_changes / max(len(points) - 2, 1)

        if angles:
            angle_changes = [abs(angles[i] - angles[i - 1]) for i in range(1, len(angles))]
            features.path_curvature = float(np.mean(angle_changes)) if angle_changes else 0.0

        path_len = features.total_distance
        if path_len > 0:
            features.movement_efficiency = features.total_displacement / path_len

        speeds = []
        for i in range(1, len(points)):
            dx = points[i].x - points[i - 1].x
            dy = points[i].y - points[i - 1].y
            dt = points[i].timestamp - points[i - 1].timestamp
            if dt > 0:
                speeds.append(math.sqrt(dx * dx + dy * dy) / (dt / 1000.0))

        if len(speeds) >= 3:
            jerks = [abs(speeds[i] - speeds[i - 1]) for i in range(1, len(speeds))]
            features.jerkiness = float(np.mean(jerks)) if jerks else 0.0

        pause_count = sum(
            1 for i in range(1, len(points))
            if (points[i].timestamp - points[i - 1].timestamp) >= self.pause_threshold_ms
        )
        features.pause_count = pause_count

        if len(points) > 1 and features.total_distance > 0:
            dx = (points[-1].x - points[0].x)
            dy = (points[-1].y - points[0].y)
            features.entry_angle = math.degrees(math.atan2(dy, dx))

    def to_dict(self, features: MouseFeatures) -> dict:
        return {
            "total_distance": round(features.total_distance, 2),
            "total_displacement": round(features.total_displacement, 2),
            "avg_speed": round(features.avg_speed, 2),
            "max_speed": round(features.max_speed, 2),
            "min_speed": round(features.min_speed, 2),
            "std_speed": round(features.std_speed, 2),
            "avg_acceleration": round(features.avg_acceleration, 2),
            "max_acceleration": round(features.max_acceleration, 2),
            "std_acceleration": round(features.std_acceleration, 2),
            "total_clicks": features.total_clicks,
            "total_right_clicks": features.total_right_clicks,
            "double_click_count": features.double_click_count,
            "avg_click_interval": round(features.avg_click_interval, 2),
            "std_click_interval": round(features.std_click_interval, 2),
            "avg_double_click_interval": round(features.avg_double_click_interval, 2),
            "idle_periods": features.idle_periods,
            "avg_idle_duration": round(features.avg_idle_duration, 2),
            "longest_idle": round(features.longest_idle, 2),
            "path_curvature": round(features.path_curvature, 4),
            "direction_changes": features.direction_changes,
            "direction_change_ratio": round(features.direction_change_ratio, 4),
            "x_range": round(features.x_range, 2),
            "y_range": round(features.y_range, 2),
            "x_std": round(features.x_std, 2),
            "y_std": round(features.y_std, 2),
            "entry_angle": round(features.entry_angle, 2),
            "movement_efficiency": round(features.movement_efficiency, 4),
            "jerkiness": round(features.jerkiness, 2),
            "pause_count": features.pause_count,
        }
