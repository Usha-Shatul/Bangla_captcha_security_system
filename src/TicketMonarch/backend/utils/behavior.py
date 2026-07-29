import math
import logging

log = logging.getLogger(__name__)

_vectorizer = None
_classifier = None
_classifier_checked = False


def _get_vectorizer():
    global _vectorizer
    if _vectorizer is None:
        from behavioral_biometrics import FeatureVectorizer
        _vectorizer = FeatureVectorizer()
    return _vectorizer


def _get_classifier():
    global _classifier, _classifier_checked
    if _classifier_checked:
        return _classifier
    _classifier_checked = True
    try:
        from classifier.predict import BanglaCaptchaClassifier
        clf = BanglaCaptchaClassifier()
        if clf.load():
            _classifier = clf
            log.info("XGBoost classifier loaded successfully")
        else:
            log.warning("XGBoost model not found — using heuristic fallback")
    except Exception as e:
        log.warning("Classifier unavailable (%s) — using heuristic fallback", e)
    return _classifier


def extract_behavior_features(keyboard_data: dict, mouse_data: dict) -> dict:
    mouse_events = mouse_data.get("mouse_events", [])
    kb_events = keyboard_data.get("keyboard_events", [])

    vec = _get_vectorizer()
    profile = vec.extract(mouse_events=mouse_events, keyboard_events=kb_events)

    result = {
        "total_keystrokes": profile.keyboard.total_keystrokes if profile.keyboard else 0,
        "avg_hold_duration": profile.keyboard.avg_dwell_time if profile.keyboard else 0,
        "typing_rhythm_std": profile.keyboard.std_dwell_time if profile.keyboard else 0,
        "has_paste": 1 if (profile.keyboard and profile.keyboard.paste_events > 0) else 0,
        "total_clicks": profile.mouse.total_clicks if profile.mouse else 0,
        "avg_mouse_speed": profile.mouse.avg_speed if profile.mouse else 0,
        "mouse_path_length": profile.mouse.total_distance if profile.mouse else 0,
        "idle_periods": profile.mouse.idle_periods if profile.mouse else 0,
        "has_context_menu": 0,
        "mouse_speed_std": profile.mouse.std_speed if profile.mouse else 0,
        "mouse_speed_max": profile.mouse.max_speed if profile.mouse else 0,
        "mouse_speed_min": profile.mouse.min_speed if profile.mouse else 0,
        "mouse_x_range": profile.mouse.x_range if profile.mouse else 0,
        "mouse_y_range": profile.mouse.y_range if profile.mouse else 0,
        "typing_interval_mean": profile.keyboard.avg_flight_time if profile.keyboard else 0,
        "typing_speed_cpm": profile.keyboard.typing_speed_cpm if profile.keyboard else 0,
        "digraph_consistency": profile.keyboard.digraph_consistency if profile.keyboard else 0,
        "correction_ratio": profile.keyboard.correction_ratio if profile.keyboard else 0,
        "movement_efficiency": profile.mouse.movement_efficiency if profile.mouse else 0,
        "path_curvature": profile.mouse.path_curvature if profile.mouse else 0,
        "jerkiness": profile.mouse.jerkiness if profile.mouse else 0,
    }

    for event in mouse_events:
        if event.get("type") == "contextmenu":
            result["has_context_menu"] = 1
            break

    return result


def compute_bot_score(features: dict) -> float:
    clf = _get_classifier()
    if clf is not None:
        try:
            kb_events = features.get("_raw_keyboard_events", [])
            ms_events = features.get("_raw_mouse_events", [])
            result = clf.predict(
                mouse_events=ms_events,
                keyboard_events=kb_events,
            )
            return result.get("bot_probability", 0.0)
        except Exception as e:
            log.warning("Classifier predict failed: %s — falling back to heuristic", e)

    return _compute_heuristic(features)


def compute_bot_score_with_events(
    keyboard_data: dict, mouse_data: dict, threshold: float = 0.5
) -> dict:
    kb_events = keyboard_data.get("keyboard_events", [])
    ms_events = mouse_data.get("mouse_events", [])

    features = extract_behavior_features(keyboard_data, mouse_data)

    clf = _get_classifier()
    if clf is not None:
        try:
            result = clf.predict(
                mouse_events=ms_events,
                keyboard_events=kb_events,
            )
            return {
                "bot_score": result["bot_probability"],
                "is_bot": result["is_bot"],
                "confidence": result["confidence"],
                "method": "xgboost",
                "features": features,
            }
        except Exception as e:
            log.warning("Classifier predict failed: %s — falling back to heuristic", e)

    score = _compute_heuristic(features)
    return {
        "bot_score": score,
        "is_bot": score >= threshold,
        "confidence": 1.0 - abs(score - 0.5) * 2,
        "method": "heuristic",
        "features": features,
    }


def _compute_heuristic(features: dict) -> float:
    score = 0.0
    weights = {
        "has_paste": 0.25,
        "has_context_menu": 0.15,
        "typing_rhythm_std": 0.15,
        "avg_mouse_speed": 0.10,
        "mouse_speed_std": 0.10,
        "idle_periods": 0.10,
        "avg_hold_duration": 0.10,
        "mouse_path_length": 0.05,
        "typing_speed_cpm": 0.05,
        "correction_ratio": 0.05,
    }

    if features.get("has_paste", 0):
        score += weights["has_paste"]

    if features.get("has_context_menu", 0):
        score += weights["has_context_menu"]

    rhythm = features.get("typing_rhythm_std", 0)
    if rhythm < 10:
        score += weights["typing_rhythm_std"]
    elif rhythm < 50:
        score += weights["typing_rhythm_std"] * 0.5

    speed = features.get("avg_mouse_speed", 0)
    if speed > 5000:
        score += weights["avg_mouse_speed"]
    elif speed > 2000:
        score += weights["avg_mouse_speed"] * 0.5

    speed_std = features.get("mouse_speed_std", 0)
    if speed_std < 5:
        score += weights["mouse_speed_std"]
    elif speed_std < 20:
        score += weights["mouse_speed_std"] * 0.5

    idles = features.get("idle_periods", 0)
    if idles == 0:
        score += weights["idle_periods"]
    elif idles <= 1:
        score += weights["idle_periods"] * 0.5

    hold = features.get("avg_hold_duration", 0)
    if hold < 30:
        score += weights["avg_hold_duration"]
    elif hold < 80:
        score += weights["avg_hold_duration"] * 0.5

    path = features.get("mouse_path_length", 0)
    if 0 < path < 200:
        score += weights["mouse_path_length"]

    cpm = features.get("typing_speed_cpm", 0)
    if cpm > 300:
        score += weights["typing_speed_cpm"]
    elif cpm > 200:
        score += weights["typing_speed_cpm"] * 0.5

    corr = features.get("correction_ratio", 0)
    if corr < 0.01 and features.get("total_keystrokes", 0) > 20:
        score += weights["correction_ratio"]

    return min(score, 1.0)
