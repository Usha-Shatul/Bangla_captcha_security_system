from flask import Blueprint, request, jsonify, session
import logging
import uuid
import json
from database.models import get_db
from utils.captcha import EasyCaptchaLoader, MediumCaptchaLoader
from utils.behavior import compute_bot_score_with_events
from utils.rl_agent import get_security_action, update_rl
from config import Config

log = logging.getLogger(__name__)
captcha_bp = Blueprint("captcha", __name__)

_easy_loader = None
_medium_loader = None


def _get_easy_loader():
    global _easy_loader
    if _easy_loader is None:
        _easy_loader = EasyCaptchaLoader(Config.EASY_CAPTCHA_DATASET_DIR)
    return _easy_loader


def _get_medium_loader():
    global _medium_loader
    if _medium_loader is None:
        _medium_loader = MediumCaptchaLoader(
            dataset_dir=Config.MEDIUM_CAPTCHA_DATASET_DIR,
            grid_size=Config.MEDIUM_GRID_SIZE,
            target_min=Config.MEDIUM_TARGET_MIN,
            target_max=Config.MEDIUM_TARGET_MAX,
        )
    return _medium_loader


@captcha_bp.route("/api/captcha/generate", methods=["POST"])
def generate_captcha():
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id", session.get("user_id"))
        difficulty = data.get("difficulty", 2)
        difficulty = max(1, min(difficulty, Config.DIFFICULTY_LEVELS))
        session_id = data.get("session_id") or str(uuid.uuid4())[:12]

        captcha_type = "easy" if difficulty <= 1 else "medium"

        if captcha_type == "easy":
            return _generate_easy(session_id, user_id, difficulty)
        else:
            return _generate_medium(session_id, user_id, difficulty)

    except Exception as e:
        log.exception("captcha generate error")
        return jsonify({"ok": False, "error": str(e)}), 500


def _generate_easy(session_id, user_id, difficulty):
    loader = _get_easy_loader()
    sample = loader.sample()

    if sample is None:
        return jsonify({
            "ok": False,
            "error": "Easy CAPTCHA dataset not available. Add images to datasets/easy/ with metadata.json.",
        }), 503

    try:
        db = get_db()
        db.execute(
            """INSERT INTO captcha_sessions
               (session_id, user_id, word_list, difficulty, used)
               VALUES (%s, %s, %s, %s, 0)
               ON DUPLICATE KEY UPDATE
               word_list = VALUES(word_list),
               difficulty = VALUES(difficulty),
               solved = 0, used = 0""",
            (session_id, user_id, json.dumps({
                "captcha_type": "easy",
                "label": sample["label"],
                "filename": sample["filename"],
            }), difficulty),
        )
        db.commit()
    except Exception as db_err:
        log.warning("DB write failed: %s", db_err)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "captcha_type": "easy",
        "image": sample["image"],
        "difficulty": difficulty,
    })


def _generate_medium(session_id, user_id, difficulty):
    loader = _get_medium_loader()
    sample = loader.sample()

    if sample is None:
        return jsonify({
            "ok": False,
            "error": "Medium CAPTCHA dataset not available. Add category images to datasets/medium/<category>/.",
        }), 503

    grid_for_storage = [
        {"position": g["position"], "category": g["category"],
         "is_target": g["is_target"], "filename": g["filename"]}
        for g in sample["grid"]
    ]

    try:
        db = get_db()
        db.execute(
            """INSERT INTO captcha_sessions
               (session_id, user_id, word_list, difficulty, used)
               VALUES (%s, %s, %s, %s, 0)
               ON DUPLICATE KEY UPDATE
               word_list = VALUES(word_list),
               difficulty = VALUES(difficulty),
               solved = 0, used = 0""",
            (session_id, user_id, json.dumps({
                "captcha_type": "medium",
                "target_category": sample["target_category"],
                "target_label_bn": sample["target_label_bn"],
                "grid": grid_for_storage,
            }), difficulty),
        )
        db.commit()
    except Exception as db_err:
        log.warning("DB write failed: %s", db_err)
    finally:
        try:
            db.close()
        except Exception:
            pass

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "captcha_type": "medium",
        "target_category": sample["target_category"],
        "target_label_bn": sample["target_label_bn"],
        "target_label_en": sample["target_label_en"],
        "grid": [
            {"position": g["position"], "image": g["image"], "filename": g["filename"]}
            for g in sample["grid"]
        ],
        "grid_size": sample["grid_size"],
        "difficulty": difficulty,
    })


@captcha_bp.route("/api/captcha/verify", methods=["POST"])
def verify_captcha():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"ok": False, "error": "No data provided"}), 400

        session_id = data.get("session_id")
        user_input = data.get("words", [])
        selected_positions = data.get("selected_positions", [])
        mouse_events = data.get("mouse", [])
        keyboard_events = data.get("keyboard", [])
        difficulty = data.get("difficulty", 2)
        solve_time_ms = data.get("solve_time_ms", 0)

        keyboard_data = {"keyboard_events": keyboard_events}
        mouse_data = {"mouse_events": mouse_events}

        bot_result = compute_bot_score_with_events(
            keyboard_data=keyboard_data,
            mouse_data=mouse_data,
        )

        bot_score = bot_result.get("bot_score", 0.0)
        is_bot = bot_result.get("is_bot", False)
        confidence = bot_result.get("confidence", 0.5)

        is_correct = _check_answer(session_id, user_input, selected_positions)

        reward = 1.0 if is_correct else -0.5
        if is_bot and is_correct:
            reward -= 0.8
        elif not is_bot and is_correct:
            reward += 0.3

        rl_decision = get_security_action(
            features=bot_result.get("features", {}),
            keyboard_events=keyboard_events,
            mouse_events=mouse_events,
            previous_difficulty=difficulty,
            attempt_count=1,
            session_duration_ms=solve_time_ms,
            bot_score=bot_score,
            confidence=confidence,
        )

        update_rl(
            features=bot_result.get("features", {}),
            action=rl_decision["action"],
            reward=reward,
            keyboard_events=keyboard_events,
            mouse_events=mouse_events,
            done=True,
            previous_difficulty=difficulty,
            attempt_count=1,
            session_duration_ms=solve_time_ms,
            bot_score=bot_score,
            confidence=confidence,
        )

        if is_bot and is_correct:
            _flag_session(session_id, bot_score, confidence)

        return jsonify({
            "ok": True,
            "correct": is_correct,
            "bot_score": bot_score,
            "is_bot": is_bot,
            "confidence": confidence,
            "security_action": rl_decision,
            "reward": reward,
        })
    except Exception as e:
        log.exception("captcha verify error")
        return jsonify({"ok": False, "error": str(e)}), 500


def _check_answer(session_id, user_input, selected_positions) -> bool:
    db = None
    try:
        db = get_db()
        if not session_id:
            return False

        row = db.execute(
            "SELECT word_list, difficulty FROM captcha_sessions WHERE session_id = %s",
            (session_id,),
        ).fetchone()
        if not row:
            return False

        stored = json.loads(row["word_list"])
        captcha_type = stored.get("captcha_type", "easy")

        correct = False
        if captcha_type == "easy":
            label = stored.get("label", "")
            if isinstance(user_input, str):
                user_input = user_input.strip()
            else:
                user_input = " ".join(user_input) if isinstance(user_input, list) else str(user_input)
            correct = user_input.strip() == label.strip()

        elif captcha_type == "medium":
            target_category = stored.get("target_category", "")
            grid = stored.get("grid", [])
            loader = _get_medium_loader()
            result = loader.verify(
                grid=grid,
                selected_positions=selected_positions or [],
                target_category=target_category,
            )
            correct = result["correct"]

        db.execute(
            "UPDATE captcha_sessions SET used = 1, solved = %s WHERE session_id = %s",
            (1 if correct else 0, session_id),
        )
        db.commit()
        return correct

    except Exception as e:
        log.warning("check_answer error: %s", e)
        return False
    finally:
        if db:
            db.close()


def _flag_session(session_id, bot_score, confidence):
    log.warning(
        "Bot detected: session=%s score=%.3f conf=%.3f",
        session_id, bot_score, confidence,
    )
