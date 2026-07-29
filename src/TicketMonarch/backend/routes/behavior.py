from flask import Blueprint, request, jsonify
import logging
import uuid
import json
from database.models import get_db
from utils.behavior import compute_bot_score_with_events
from utils.rl_agent import get_security_action

log = logging.getLogger(__name__)
behavior_bp = Blueprint("behavior", __name__)


@behavior_bp.route("/api/behavior/track", methods=["POST"])
def track_behavior():
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

        session_id = str(uuid.uuid4())[:12]

        try:
            db = get_db()
            db.execute(
                """INSERT INTO behavior_logs
                   (session_id, user_ip, mouse_events, keyboard_events,
                    bot_score, is_bot, confidence, method,
                    features_json, events_json)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    session_id,
                    request.remote_addr or "unknown",
                    len(mouse_events),
                    len(keyboard_events),
                    bot_result.get("bot_score", 0),
                    1 if bot_result.get("is_bot") else 0,
                    bot_result.get("confidence", 0),
                    bot_result.get("method", "unknown"),
                    json.dumps(bot_result.get("features", {})),
                    json.dumps({
                        "mouse": mouse_events[:100],
                        "keyboard": keyboard_events[:100],
                        "touch": touch_events[:50],
                        "scroll": scroll_events[:50],
                    }),
                ),
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
            "bot_score": bot_result.get("bot_score", 0),
            "is_bot": bot_result.get("is_bot", False),
            "confidence": bot_result.get("confidence", 0.5),
            "method": bot_result.get("method", "unknown"),
            "security_action": rl_decision,
        })
    except Exception as e:
        log.exception("behavior track error")
        return jsonify({"ok": False, "error": str(e)}), 500


@behavior_bp.route("/api/behavior/history", methods=["GET"])
def behavior_history():
    try:
        db = get_db()
        rows = db.execute(
            """SELECT id, session_id, user_ip, mouse_events, keyboard_events,
                      bot_score, is_bot, confidence, method, created_at
               FROM behavior_logs
               ORDER BY created_at DESC
               LIMIT 50"""
        ).fetchall()
        logs = [
            {
                "id": r["id"], "session_id": r["session_id"], "user_ip": r["user_ip"],
                "mouse_events": r["mouse_events"], "keyboard_events": r["keyboard_events"],
                "bot_score": r["bot_score"], "is_bot": r["is_bot"], "confidence": r["confidence"],
                "method": r["method"], "created_at": r["created_at"],
            }
            for r in rows
        ]
        return jsonify({"ok": True, "logs": logs})
    except Exception as e:
        log.exception("behavior history error")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        try:
            db.close()
        except Exception:
            pass


@behavior_bp.route("/api/behavior/stats", methods=["GET"])
def behavior_stats():
    try:
        db = get_db()
        total = db.execute("SELECT COUNT(*) as cnt FROM behavior_logs").fetchone()["cnt"]
        bots = db.execute("SELECT COUNT(*) as cnt FROM behavior_logs WHERE is_bot = 1").fetchone()["cnt"]
        avg_score = db.execute("SELECT AVG(bot_score) as avg_s FROM behavior_logs").fetchone()["avg_s"] or 0
        method_rows = db.execute(
            """SELECT method, COUNT(*) as cnt
               FROM behavior_logs
               GROUP BY method
               ORDER BY cnt DESC"""
        ).fetchall()
        method_counts = {r["method"]: r["cnt"] for r in method_rows}
        label_rows = db.execute(
            """SELECT label, COUNT(*) as cnt
               FROM behavior_logs
               GROUP BY label
               ORDER BY cnt DESC"""
        ).fetchall()
        label_counts = {r["label"]: r["cnt"] for r in label_rows}
        return jsonify({
            "ok": True,
            "total_sessions": total,
            "detected_bots": bots,
            "human_sessions": total - bots,
            "avg_bot_score": round(avg_score, 4),
            "method_distribution": method_counts,
            "label_distribution": label_counts,
        })
    except Exception as e:
        log.exception("behavior stats error")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        try:
            db.close()
        except Exception:
            pass


@behavior_bp.route("/api/behavior/label", methods=["POST"])
def label_behavior():
    db = None
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")
        label = data.get("label")

        if not session_id or label not in ("human", "bot", "unknown"):
            return jsonify({"ok": False, "error": "Provide session_id and label (human/bot/unknown)"}), 400

        db = get_db()
        cursor = db.execute(
            "UPDATE behavior_logs SET label = %s WHERE session_id = %s",
            (label, session_id),
        )
        db.commit()
        updated = cursor.rowcount

        return jsonify({"ok": True, "updated": updated})
    except Exception as e:
        log.exception("label behavior error")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        if db:
            db.close()


@behavior_bp.route("/api/behavior/label/bulk", methods=["POST"])
def label_bulk():
    db = None
    try:
        data = request.get_json(force=True)
        labels = data.get("labels", [])

        if not labels:
            return jsonify({"ok": False, "error": "Provide labels list [{session_id, label}]"}), 400

        db = get_db()
        total = 0
        for item in labels:
            sid = item.get("session_id")
            lbl = item.get("label")
            if sid and lbl in ("human", "bot", "unknown"):
                cursor = db.execute(
                    "UPDATE behavior_logs SET label = %s WHERE session_id = %s",
                    (lbl, sid),
                )
                total += cursor.rowcount
        db.commit()

        return jsonify({"ok": True, "updated": total})
    except Exception as e:
        log.exception("bulk label error")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        if db:
            db.close()


@behavior_bp.route("/api/dataset/export", methods=["POST"])
def dataset_export():
    try:
        data = request.get_json(silent=True) or {}
        output_format = data.get("format", "json")
        scope = data.get("scope", "full")

        from utils.dataset import (
            export_behavior_logs,
            export_rl_episodes,
            export_captcha_sessions,
            export_full_dataset,
        )

        if scope == "full":
            result = export_full_dataset(output_format)
        elif scope == "behavior":
            result = export_behavior_logs(output_format)
        elif scope == "rl":
            result = export_rl_episodes(output_format)
        elif scope == "captcha":
            result = export_captcha_sessions(output_format)
        else:
            return jsonify({"ok": False, "error": f"Unknown scope: {scope}"}), 400

        return jsonify({"ok": True, **result})
    except Exception as e:
        log.exception("dataset export error")
        return jsonify({"ok": False, "error": str(e)}), 500


@behavior_bp.route("/api/dataset/stats", methods=["GET"])
def dataset_stats():
    try:
        from utils.dataset import get_dataset_stats
        stats = get_dataset_stats()
        return jsonify({"ok": True, **stats})
    except Exception as e:
        log.exception("dataset stats error")
        return jsonify({"ok": False, "error": str(e)}), 500
