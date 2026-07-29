from flask import Blueprint, request, jsonify
import json
import logging
from database.models import get_db
from utils.behavior import compute_bot_score_with_events
from utils.rl_agent import get_security_action, SECURITY_ACTIONS

log = logging.getLogger(__name__)
dev_bp = Blueprint("dev", __name__)

ACTION_COLORS = {
    0: "#16a34a",
    1: "#d97706",
    2: "#2563eb",
    3: "#7c3aed",
    4: "#dc2626",
    5: "#a855f7",
    6: "#991b1b",
}


@dev_bp.route("/api/dev/sessions", methods=["GET"])
def dev_sessions():
    try:
        db = get_db()
        try:
            limit = min(int(request.args.get("limit", 20)), 100)
            rows = db.execute(
                """SELECT id, session_id, user_ip, mouse_events, keyboard_events,
                          bot_score, is_bot, confidence, method, label,
                          features_json, events_json, created_at
                   FROM behavior_logs
                   ORDER BY created_at DESC
                   LIMIT %s""",
                (limit,),
            ).fetchall()
        finally:
            db.close()

        sessions = []
        for r in rows:
            features = {}
            try:
                features = json.loads(r["features_json"]) if r["features_json"] else {}
            except (json.JSONDecodeError, TypeError):
                pass

            events = {}
            try:
                events = json.loads(r["events_json"]) if r["events_json"] else {}
            except (json.JSONDecodeError, TypeError):
                pass

            mouse_count = r["mouse_events"] or len(events.get("mouse", []))
            keyboard_count = r["keyboard_events"] or len(events.get("keyboard", []))

            sessions.append({
                "id": r["id"],
                "session_id": r["session_id"],
                "user_ip": r["user_ip"],
                "mouse_events": mouse_count,
                "keyboard_events": keyboard_count,
                "bot_score": r["bot_score"],
                "is_bot": bool(r["is_bot"]),
                "confidence": r["confidence"],
                "method": r["method"],
                "label": r["label"],
                "created_at": str(r["created_at"]) if r["created_at"] else None,
            })

        return jsonify({"ok": True, "sessions": sessions, "total": len(sessions)})
    except Exception as e:
        log.exception("dev sessions error")
        return jsonify({"ok": False, "error": str(e)}), 500


@dev_bp.route("/api/dev/session/<session_id>", methods=["GET"])
def dev_session_detail(session_id):
    try:
        db = get_db()
        try:
            row = db.execute(
                """SELECT id, session_id, user_ip, mouse_events, keyboard_events,
                          bot_score, is_bot, confidence, method, label,
                          features_json, events_json, created_at
                   FROM behavior_logs
                   WHERE session_id = %s
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (session_id,),
            ).fetchone()

            if not row:
                return jsonify({"ok": False, "error": "Session not found"}), 404

            features = {}
            try:
                features = json.loads(row["features_json"]) if row["features_json"] else {}
            except (json.JSONDecodeError, TypeError):
                pass

            events = {}
            try:
                events = json.loads(row["events_json"]) if row["events_json"] else {}
            except (json.JSONDecodeError, TypeError):
                pass

            mouse_events_raw = events.get("mouse", [])
            keyboard_events_raw = events.get("keyboard", [])

            rl_decision = get_security_action(
                features=features,
                keyboard_events=keyboard_events_raw,
                mouse_events=mouse_events_raw,
                previous_difficulty=1,
                attempt_count=0,
                session_duration_ms=0,
                bot_score=row["bot_score"],
                confidence=row["confidence"],
            )

            action_probs = {}
            total_actions = 7
            chosen_action = rl_decision.get("action", 0)
            for i in range(total_actions):
                if i == chosen_action:
                    action_probs[SECURITY_ACTIONS.get(i, f"action_{i}")] = 0.95
                else:
                    action_probs[SECURITY_ACTIONS.get(i, f"action_{i}")] = 0.05 / max(total_actions - 1, 1)

            feature_breakdown = {
                "mouse_speed_avg": features.get("mouse_speed_avg", features.get("avg_mouse_speed", 0)),
                "mouse_speed_std": features.get("mouse_speed_std", 0),
                "click_frequency": features.get("click_frequency", 0),
                "mouse_path_length": features.get("mouse_path_length", 0),
                "idle_ratio": features.get("idle_ratio", 0),
                "typing_speed": features.get("typing_speed", 0),
                "typing_rhythm_std": features.get("typing_rhythm_std", features.get("typing_rhythm", 0)),
                "hold_duration_avg": features.get("hold_duration_avg", 0),
                "backspace_rate": features.get("backspace_rate", 0),
                "paste_ratio": features.get("paste_ratio", 0),
            }

            timeline = []
            for ev in mouse_events_raw[:200]:
                timeline.append({
                    "type": "mouse",
                    "x": ev.get("x", 0),
                    "y": ev.get("y", 0),
                    "speed": ev.get("speed", 0),
                    "click": ev.get("click_type", "") == "click",
                    "timestamp": ev.get("timestamp", 0),
                })
            for ev in keyboard_events_raw[:200]:
                timeline.append({
                    "type": "keyboard",
                    "key": ev.get("key", ""),
                    "hold": ev.get("hold_duration", 0),
                    "interval": ev.get("interval", 0),
                    "timestamp": ev.get("timestamp", 0),
                })
            timeline.sort(key=lambda e: e.get("timestamp", 0))
        finally:
            db.close()

        return jsonify({
            "ok": True,
            "session": {
                "id": row["id"],
                "session_id": row["session_id"],
                "user_ip": row["user_ip"],
                "mouse_events": row["mouse_events"] or len(mouse_events_raw),
                "keyboard_events": row["keyboard_events"] or len(keyboard_events_raw),
                "bot_score": row["bot_score"],
                "is_bot": bool(row["is_bot"]),
                "confidence": row["confidence"],
                "method": row["method"],
                "label": row["label"],
                "created_at": str(row["created_at"]) if row["created_at"] else None,
            },
            "security_action": rl_decision,
            "action_probs": action_probs,
            "feature_breakdown": feature_breakdown,
            "timeline": timeline,
            "state_vector": rl_decision.get("state", []),
        })
    except Exception as e:
        log.exception("dev session detail error")
        return jsonify({"ok": False, "error": str(e)}), 500
