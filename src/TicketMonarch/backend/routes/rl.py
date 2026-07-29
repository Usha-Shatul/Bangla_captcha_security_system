from flask import Blueprint, request, jsonify
import logging
from database.models import get_db
from utils.behavior import compute_bot_score_with_events
from utils.rl_agent import get_security_action, update_rl

log = logging.getLogger(__name__)
rl_bp = Blueprint("rl", __name__)


@rl_bp.route("/api/rl/difficulty", methods=["POST"])
def rl_difficulty():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"ok": False, "error": "No data provided"}), 400

        mouse_events = data.get("mouse", [])
        keyboard_events = data.get("keyboard", [])
        touch_events = data.get("touch", [])
        scroll_events = data.get("scroll", [])
        previous_difficulty = data.get("previous_difficulty", 1)
        attempt_count = data.get("attempt_count", 0)
        session_duration_ms = data.get("session_duration_ms", 0.0)

        keyboard_data = {"keyboard_events": keyboard_events}
        mouse_data = {"mouse_events": mouse_events}
        bot_result = compute_bot_score_with_events(
            keyboard_data=keyboard_data,
            mouse_data=mouse_data,
        )

        features = bot_result.get("features", {})
        rl_decision = get_security_action(
            features=features,
            keyboard_events=keyboard_events,
            mouse_events=mouse_events,
            previous_difficulty=previous_difficulty,
            attempt_count=attempt_count,
            session_duration_ms=session_duration_ms,
            bot_score=bot_result.get("bot_score", 0.0),
            confidence=bot_result.get("confidence", 0.5),
        )

        try:
            db = get_db()
            try:
                db.execute(
                    """INSERT INTO rl_episodes
                       (session_id, action, action_name, difficulty, reward, is_bot, bot_score)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        data.get("session_id", "unknown"),
                        rl_decision["action"],
                        rl_decision.get("action_name", "unknown"),
                        rl_decision.get("difficulty", 2),
                        0.0,
                        1 if bot_result.get("is_bot") else 0,
                        bot_result.get("bot_score", 0.0),
                    ),
                )
                db.commit()
            finally:
                db.close()
        except Exception as db_err:
            log.warning("DB write failed: %s", db_err)

        return jsonify({
            "ok": True,
            "security_action": rl_decision,
            "bot_score": bot_result.get("bot_score", 0),
            "confidence": bot_result.get("confidence", 0.5),
        })
    except Exception as e:
        log.exception("rl difficulty error")
        return jsonify({"ok": False, "error": str(e)}), 500


@rl_bp.route("/api/rl/reward", methods=["POST"])
def rl_reward():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"ok": False, "error": "No data provided"}), 400

        mouse_events = data.get("mouse", [])
        keyboard_events = data.get("keyboard", [])
        action = data.get("action", 2)
        reward = data.get("reward", 0.0)
        done = data.get("done", False)
        previous_difficulty = data.get("previous_difficulty", 1)
        attempt_count = data.get("attempt_count", 0)
        session_duration_ms = data.get("session_duration_ms", 0.0)

        keyboard_data = {"keyboard_events": keyboard_events}
        mouse_data = {"mouse_events": mouse_events}
        bot_result = compute_bot_score_with_events(
            keyboard_data=keyboard_data,
            mouse_data=mouse_data,
        )

        features = bot_result.get("features", {})
        update_rl(
            features=features,
            action=action,
            reward=reward,
            keyboard_events=keyboard_events,
            mouse_events=mouse_events,
            done=done,
            previous_difficulty=previous_difficulty,
            attempt_count=attempt_count,
            session_duration_ms=session_duration_ms,
            bot_score=bot_result.get("bot_score", 0.0),
            confidence=bot_result.get("confidence", 0.5),
        )

        return jsonify({"ok": True, "updated": True})
    except Exception as e:
        log.exception("rl reward error")
        return jsonify({"ok": False, "error": str(e)}), 500


@rl_bp.route("/api/rl/stats", methods=["GET"])
def rl_stats():
    try:
        from utils.rl_agent import get_rl_agent
        agent = get_rl_agent()
        q_table_size = len(agent.q_table) if hasattr(agent, "q_table") else 0

        db = get_db()
        try:
            total_episodes = db.execute("SELECT COUNT(*) as cnt FROM rl_episodes").fetchone()["cnt"]
            avg_reward = db.execute("SELECT AVG(reward) as avg_r FROM rl_episodes").fetchone()["avg_r"] or 0
        finally:
            db.close()

        return jsonify({
            "ok": True,
            "q_table_size": q_table_size,
            "total_episodes": total_episodes,
            "avg_reward": round(avg_reward, 4),
            "num_actions": 7,
            "actions": {
                0: "allow",
                1: "observe",
                2: "captcha_easy",
                3: "captcha_medium",
                4: "captcha_hard",
                5: "honeypot",
                6: "block",
            },
        })
    except Exception as e:
        log.exception("rl stats error")
        return jsonify({"ok": False, "error": str(e)}), 500


@rl_bp.route("/api/rl/qtable", methods=["GET"])
def rl_qtable():
    try:
        from utils.rl_agent import get_rl_agent
        agent = get_rl_agent()
        return jsonify({
            "ok": True,
            "q_table": agent.q_table if hasattr(agent, "q_table") else {},
        })
    except Exception as e:
        log.exception("rl qtable error")
        return jsonify({"ok": False, "error": str(e)}), 500
