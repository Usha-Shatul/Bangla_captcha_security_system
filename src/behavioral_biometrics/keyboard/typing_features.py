import math
import numpy as np
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class KeystrokeEvent:
    key: str
    key_down_time: float
    key_up_time: float
    is_modifier: bool = False
    key_code: str = ""


@dataclass
class Digraph:
    key1: str
    key2: str
    flight_time: float
    dwell_time: float
    total_time: float


@dataclass
class TypingFeatures:
    total_keystrokes: int = 0
    total_keys_held: int = 0
    avg_dwell_time: float = 0.0
    std_dwell_time: float = 0.0
    max_dwell_time: float = 0.0
    min_dwell_time: float = 0.0
    median_dwell_time: float = 0.0
    avg_flight_time: float = 0.0
    std_flight_time: float = 0.0
    max_flight_time: float = 0.0
    min_flight_time: float = 0.0
    median_flight_time: float = 0.0
    avg_total_time: float = 0.0
    std_total_time: float = 0.0
    typing_speed_cpm: float = 0.0
    typing_speed_kpm: float = 0.0
    avg_speed_std: float = 0.0
    rhythm_regularity: float = 0.0
    num_digraphs: int = 0
    unique_digraphs: int = 0
    avg_digraph_flight: float = 0.0
    std_digraph_flight: float = 0.0
    avg_digraph_dwell: float = 0.0
    correction_count: int = 0
    correction_ratio: float = 0.0
    paste_events: int = 0
    paste_chars: int = 0
    delete_presses: int = 0
    backspace_ratio: float = 0.0
    modifier_usage_ratio: float = 0.0
    pause_count: int = 0
    avg_pause_duration: float = 0.0
    longest_pause: float = 0.0
    typing_bursts: int = 0
    avg_burst_length: float = 0.0
    key_intensity_variation: float = 0.0
    error_rate: float = 0.0
    digraph_consistency: float = 0.0
    flight_dwell_ratio: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class TypingFeatureExtractor:
    def __init__(
        self,
        pause_threshold_ms: float = 2000.0,
        burst_threshold_ms: float = 500.0,
        correction_keys: tuple = ("Backspace", "Delete", "ArrowLeft", "ArrowRight"),
        modifier_keys: tuple = ("Shift", "Control", "Alt", "Meta", "CapsLock"),
    ):
        self.pause_threshold_ms = pause_threshold_ms
        self.burst_threshold_ms = burst_threshold_ms
        self.correction_keys = correction_keys
        self.modifier_keys = modifier_keys

    def extract(self, events: list[dict]) -> TypingFeatures:
        keystrokes = self._parse_events(events)
        if not keystrokes:
            return TypingFeatures()

        features = TypingFeatures()
        features.total_keystrokes = len(keystrokes)
        features.total_keys_held = sum(1 for k in keystrokes if not k.is_modifier)

        self._extract_timing_features(keystrokes, features)
        self._extract_speed_features(keystrokes, features)
        self._extract_digraph_features(keystrokes, features)
        self._extract_error_features(events, keystrokes, features)
        self._extract_pattern_features(keystrokes, features)

        return features

    def _parse_events(self, events: list[dict]) -> list[KeystrokeEvent]:
        keystrokes = []
        pending_downs = {}

        for event in events:
            etype = event.get("type", "")
            key = event.get("key", "")
            timestamp = event.get("timestamp", 0)
            key_code = event.get("code", "")
            is_modifier = key in self.modifier_keys

            if etype == "keydown":
                pending_downs[key] = timestamp
            elif etype == "keyup" and key in pending_downs:
                down_time = pending_downs.pop(key)
                keystrokes.append(
                    KeystrokeEvent(
                        key=key,
                        key_down_time=down_time,
                        key_up_time=timestamp,
                        is_modifier=is_modifier,
                        key_code=key_code,
                    )
                )

        keystrokes.sort(key=lambda k: k.key_down_time)
        return keystrokes

    def _extract_timing_features(self, keystrokes: list[KeystrokeEvent], features: TypingFeatures):
        dwell_times = [k.key_up_time - k.key_down_time for k in keystrokes if not k.is_modifier]
        flight_times = []
        total_times = []

        for i in range(1, len(keystrokes)):
            ft = keystrokes[i].key_down_time - keystrokes[i - 1].key_up_time
            if ft >= 0:
                flight_times.append(ft)
            tt = keystrokes[i].key_down_time - keystrokes[i - 1].key_down_time
            total_times.append(tt)

        if dwell_times:
            features.avg_dwell_time = float(np.mean(dwell_times))
            features.std_dwell_time = float(np.std(dwell_times)) if len(dwell_times) > 1 else 0.0
            features.max_dwell_time = max(dwell_times)
            features.min_dwell_time = min(dwell_times)
            features.median_dwell_time = float(np.median(dwell_times))

        if flight_times:
            features.avg_flight_time = float(np.mean(flight_times))
            features.std_flight_time = float(np.std(flight_times)) if len(flight_times) > 1 else 0.0
            features.max_flight_time = max(flight_times)
            features.min_flight_time = min(flight_times)
            features.median_flight_time = float(np.median(flight_times))

        if total_times:
            features.avg_total_time = float(np.mean(total_times))
            features.std_total_time = float(np.std(total_times)) if len(total_times) > 1 else 0.0

        features.flight_dwell_ratio = (
            features.avg_flight_time / features.avg_dwell_time
            if features.avg_dwell_time > 0 else 0.0
        )

    def _extract_speed_features(self, keystrokes: list[KeystrokeEvent], features: TypingFeatures):
        typing_keystrokes = [k for k in keystrokes if not k.is_modifier and k.key not in self.correction_keys]
        if len(typing_keystrokes) < 2:
            return

        durations = []
        window_size = 5
        for i in range(window_size, len(typing_keystrokes)):
            dt = typing_keystrokes[i].key_down_time - typing_keystrokes[i - window_size].key_down_time
            if dt > 0:
                speeds = [window_size / (dt / 1000.0 / window_size)]
                durations.append(speeds[0])

        if typing_keystrokes:
            total_time = (typing_keystrokes[-1].key_down_time - typing_keystrokes[0].key_down_time) / 1000.0
            if total_time > 0:
                features.typing_speed_cpm = len(typing_keystrokes) / total_time * 60.0
                features.typing_speed_kpm = len(typing_keystrokes) / total_time * 60.0 / 5.0

        window_speeds = []
        for i in range(1, len(typing_keystrokes)):
            dt = typing_keystrokes[i].key_down_time - typing_keystrokes[i - 1].key_down_time
            if dt > 0:
                window_speeds.append(1000.0 / dt)

        if len(window_speeds) > 1:
            features.avg_speed_std = float(np.std(window_speeds))

        if window_speeds and features.typing_speed_cpm > 0:
            mean_speed = np.mean(window_speeds)
            if mean_speed > 0:
                features.rhythm_regularity = float(np.std(window_speeds) / mean_speed)

    def _extract_digraph_features(self, keystrokes: list[KeystrokeEvent], features: TypingFeatures):
        typing_ks = [k for k in keystrokes if not k.is_modifier]
        digraphs = []
        seen = set()

        for i in range(1, len(typing_ks)):
            d = Digraph(
                key1=typing_ks[i - 1].key,
                key2=typing_ks[i].key,
                flight_time=typing_ks[i].key_down_time - typing_ks[i - 1].key_up_time,
                dwell_time=typing_ks[i].key_up_time - typing_ks[i].key_down_time,
                total_time=typing_ks[i].key_down_time - typing_ks[i - 1].key_down_time,
            )
            digraphs.append(d)
            seen.add((d.key1, d.key2))

        features.num_digraphs = len(digraphs)
        features.unique_digraphs = len(seen)

        if digraphs:
            flights = [d.flight_time for d in digraphs if d.flight_time >= 0]
            dwells = [d.dwell_time for d in digraphs]

            if flights:
                features.avg_digraph_flight = float(np.mean(flights))
                features.std_digraph_flight = float(np.std(flights)) if len(flights) > 1 else 0.0
            if dwells:
                features.avg_digraph_dwell = float(np.mean(dwells))

        if features.num_digraphs > 0:
            digraph_flights = {}
            for d in digraphs:
                pair = (d.key1, d.key2)
                if pair not in digraph_flights:
                    digraph_flights[pair] = []
                digraph_flights[pair].append(d.flight_time)

            consistency_values = []
            for pair, flights in digraph_flights.items():
                if len(flights) > 1:
                    mean_f = np.mean(flights)
                    if mean_f > 0:
                        consistency_values.append(float(np.std(flights) / mean_f))

            features.digraph_consistency = float(np.mean(consistency_values)) if consistency_values else 0.0

    def _extract_error_features(self, events: list[dict], keystrokes: list[KeystrokeEvent], features: TypingFeatures):
        total_presses = sum(1 for e in events if e.get("type") == "keydown")
        correction_presses = sum(
            1 for k in keystrokes if k.key in self.correction_keys
        )
        features.correction_count = correction_presses
        features.correction_ratio = correction_presses / total_presses if total_presses > 0 else 0.0

        features.paste_events = sum(1 for e in events if e.get("type") == "paste")
        features.paste_chars = sum(e.get("paste_length", 0) for e in events if e.get("type") == "paste")

        features.delete_presses = correction_presses
        typing_count = sum(1 for k in keystrokes if not k.is_modifier and k.key not in self.correction_keys)
        features.backspace_ratio = correction_presses / typing_count if typing_count > 0 else 0.0

        modifier_count = sum(1 for k in keystrokes if k.is_modifier)
        features.modifier_usage_ratio = modifier_count / total_presses if total_presses > 0 else 0.0

        features.error_rate = (
            features.correction_ratio * 0.5
        )

    def _extract_pattern_features(self, keystrokes: list[KeystrokeEvent], features: TypingFeatures):
        typing_ks = [k for k in keystrokes if not k.is_modifier]

        pauses = []
        for i in range(1, len(typing_ks)):
            gap = typing_ks[i].key_down_time - typing_ks[i - 1].key_up_time
            if gap >= self.pause_threshold_ms:
                pauses.append(gap)

        features.pause_count = len(pauses)
        if pauses:
            features.avg_pause_duration = float(np.mean(pauses))
            features.longest_pause = max(pauses)

        bursts = []
        current_burst = 1
        for i in range(1, len(typing_ks)):
            gap = typing_ks[i].key_down_time - typing_ks[i - 1].key_up_time
            if gap < self.burst_threshold_ms:
                current_burst += 1
            else:
                bursts.append(current_burst)
                current_burst = 1
        bursts.append(current_burst)

        features.typing_bursts = len(bursts)
        features.avg_burst_length = float(np.mean(bursts)) if bursts else 0.0

        dwell_times = [k.key_up_time - k.key_down_time for k in keystrokes if not k.is_modifier]
        if dwell_times and len(dwell_times) > 1:
            features.key_intensity_variation = float(np.std(dwell_times) / np.mean(dwell_times)) if np.mean(dwell_times) > 0 else 0.0

    def to_dict(self, features: TypingFeatures) -> dict:
        return {
            "total_keystrokes": features.total_keystrokes,
            "total_keys_held": features.total_keys_held,
            "avg_dwell_time": round(features.avg_dwell_time, 2),
            "std_dwell_time": round(features.std_dwell_time, 2),
            "max_dwell_time": round(features.max_dwell_time, 2),
            "min_dwell_time": round(features.min_dwell_time, 2),
            "median_dwell_time": round(features.median_dwell_time, 2),
            "avg_flight_time": round(features.avg_flight_time, 2),
            "std_flight_time": round(features.std_flight_time, 2),
            "max_flight_time": round(features.max_flight_time, 2),
            "min_flight_time": round(features.min_flight_time, 2),
            "median_flight_time": round(features.median_flight_time, 2),
            "avg_total_time": round(features.avg_total_time, 2),
            "std_total_time": round(features.std_total_time, 2),
            "typing_speed_cpm": round(features.typing_speed_cpm, 2),
            "typing_speed_kpm": round(features.typing_speed_kpm, 2),
            "avg_speed_std": round(features.avg_speed_std, 2),
            "rhythm_regularity": round(features.rhythm_regularity, 4),
            "num_digraphs": features.num_digraphs,
            "unique_digraphs": features.unique_digraphs,
            "avg_digraph_flight": round(features.avg_digraph_flight, 2),
            "std_digraph_flight": round(features.std_digraph_flight, 2),
            "avg_digraph_dwell": round(features.avg_digraph_dwell, 2),
            "correction_count": features.correction_count,
            "correction_ratio": round(features.correction_ratio, 4),
            "paste_events": features.paste_events,
            "paste_chars": features.paste_chars,
            "delete_presses": features.delete_presses,
            "backspace_ratio": round(features.backspace_ratio, 4),
            "modifier_usage_ratio": round(features.modifier_usage_ratio, 4),
            "pause_count": features.pause_count,
            "avg_pause_duration": round(features.avg_pause_duration, 2),
            "longest_pause": round(features.longest_pause, 2),
            "typing_bursts": features.typing_bursts,
            "avg_burst_length": round(features.avg_burst_length, 2),
            "key_intensity_variation": round(features.key_intensity_variation, 4),
            "error_rate": round(features.error_rate, 4),
            "digraph_consistency": round(features.digraph_consistency, 4),
            "flight_dwell_ratio": round(features.flight_dwell_ratio, 4),
        }
