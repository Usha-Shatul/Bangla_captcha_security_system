import os
import json
import csv
import logging
from datetime import datetime
from database.models import get_db

log = logging.getLogger(__name__)

EXPORT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "research_exports"
)


def export_behavior_logs(output_format="json", limit=1000):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    db = get_db()

    rows = db.execute(
        """SELECT id, session_id, user_ip, mouse_events, keyboard_events,
                  bot_score, is_bot, confidence, method, label,
                  features_json, events_json, created_at
           FROM behavior_logs
           ORDER BY created_at DESC
           LIMIT %s""",
        (limit,),
    ).fetchall()
    db.close()

    records = []
    for r in rows:
        rec = {
            "id": r["id"],
            "session_id": r["session_id"],
            "user_ip": r["user_ip"],
            "mouse_event_count": r["mouse_events"],
            "keyboard_event_count": r["keyboard_events"],
            "bot_score": r["bot_score"],
            "is_bot": r["is_bot"],
            "confidence": r["confidence"],
            "method": r["method"],
            "label": r["label"] or "unknown",
            "features": json.loads(r["features_json"]) if r["features_json"] else {},
            "events": json.loads(r["events_json"]) if r["events_json"] else {},
            "created_at": r["created_at"],
        }
        records.append(rec)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if output_format == "csv":
        path = os.path.join(EXPORT_DIR, f"behavior_logs_{ts}.csv")
        if records:
            keys = [k for k in records[0].keys() if k not in ("features", "events")]
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(records)
    else:
        path = os.path.join(EXPORT_DIR, f"behavior_logs_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False, default=str)

    log.info("Exported %d behavior logs to %s", len(records), path)
    return {"count": len(records), "path": path}


def export_rl_episodes(output_format="json", limit=1000):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    db = get_db()

    rows = db.execute(
        """SELECT id, session_id, action, action_name, difficulty,
                  reward, is_bot, bot_score, created_at
           FROM rl_episodes
           ORDER BY created_at DESC
           LIMIT %s""",
        (limit,),
    ).fetchall()
    db.close()

    records = [r if isinstance(r, dict) else dict(r) for r in rows]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if output_format == "csv":
        path = os.path.join(EXPORT_DIR, f"rl_episodes_{ts}.csv")
        if records:
            keys = list(records[0].keys())
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(records)
    else:
        path = os.path.join(EXPORT_DIR, f"rl_episodes_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False, default=str)

    log.info("Exported %d RL episodes to %s", len(records), path)
    return {"count": len(records), "path": path}


def export_captcha_sessions(output_format="json", limit=1000):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    db = get_db()

    rows = db.execute(
        """SELECT id, session_id, user_id, word_list, difficulty,
                  solved, used, created_at
           FROM captcha_sessions
           ORDER BY created_at DESC
           LIMIT %s""",
        (limit,),
    ).fetchall()
    db.close()

    records = []
    for r in rows:
        rec = {
            "id": r["id"],
            "session_id": r["session_id"],
            "user_id": r["user_id"],
            "word_list": json.loads(r["word_list"]) if r["word_list"] else [],
            "difficulty": r["difficulty"],
            "solved": r["solved"],
            "used": r["used"],
            "created_at": r["created_at"],
        }
        records.append(rec)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if output_format == "csv":
        path = os.path.join(EXPORT_DIR, f"captcha_sessions_{ts}.csv")
        if records:
            keys = [k for k in records[0].keys() if k != "word_list"]
            keys.append("word_count")
            for rec in records:
                rec["word_count"] = len(rec["word_list"])
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(records)
    else:
        path = os.path.join(EXPORT_DIR, f"captcha_sessions_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False, default=str)

    log.info("Exported %d captcha sessions to %s", len(records), path)
    return {"count": len(records), "path": path}


def export_full_dataset(output_format="json"):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_dir = os.path.join(EXPORT_DIR, f"full_dataset_{ts}")
    os.makedirs(dataset_dir, exist_ok=True)

    behavior = export_behavior_logs(output_format)
    rl = export_rl_episodes(output_format)
    captcha = export_captcha_sessions(output_format)

    summary = {
        "exported_at": datetime.now().isoformat(),
        "behavior_logs": behavior["count"],
        "rl_episodes": rl["count"],
        "captcha_sessions": captcha["count"],
        "files": {
            "behavior": behavior["path"],
            "rl_episodes": rl["path"],
            "captcha_sessions": captcha["path"],
        },
    }

    summary_path = os.path.join(dataset_dir, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    log.info("Full dataset exported to %s", dataset_dir)
    return summary


def get_dataset_stats():
    db = get_db()

    behavior_count = db.execute("SELECT COUNT(*) as cnt FROM behavior_logs").fetchone()["cnt"]
    rl_count = db.execute("SELECT COUNT(*) as cnt FROM rl_episodes").fetchone()["cnt"]
    captcha_count = db.execute("SELECT COUNT(*) as cnt FROM captcha_sessions").fetchone()["cnt"]
    booking_count = db.execute("SELECT COUNT(*) as cnt FROM bookings").fetchone()["cnt"]

    bot_count = db.execute("SELECT COUNT(*) as cnt FROM behavior_logs WHERE is_bot = 1").fetchone()["cnt"]
    avg_bot_score = db.execute("SELECT AVG(bot_score) as avg_s FROM behavior_logs").fetchone()["avg_s"] or 0

    human_labeled = db.execute("SELECT COUNT(*) as cnt FROM behavior_logs WHERE label = 'human'").fetchone()["cnt"]
    bot_labeled = db.execute("SELECT COUNT(*) as cnt FROM behavior_logs WHERE label = 'bot'").fetchone()["cnt"]

    action_dist = db.execute(
        "SELECT action_name, COUNT(*) as cnt FROM rl_episodes GROUP BY action_name"
    ).fetchall()

    difficulty_dist = db.execute(
        "SELECT difficulty, COUNT(*) as cnt FROM captcha_sessions GROUP BY difficulty"
    ).fetchall()

    solve_rate_row = db.execute(
        "SELECT COUNT(*) as total, SUM(solved) as solved FROM captcha_sessions"
    ).fetchone()
    solve_rate = (solve_rate_row["solved"] / max(solve_rate_row["total"], 1)) if solve_rate_row else 0

    db.close()

    return {
        "total_behavior_logs": behavior_count,
        "total_rl_episodes": rl_count,
        "total_captcha_sessions": captcha_count,
        "total_bookings": booking_count,
        "detected_bots": bot_count,
        "human_sessions": behavior_count - bot_count,
        "human_labeled": human_labeled,
        "bot_labeled": bot_labeled,
        "avg_bot_score": round(avg_bot_score, 4),
        "solve_rate": round(solve_rate, 4),
        "action_distribution": {r["action_name"]: r["cnt"] for r in action_dist if r["action_name"]},
        "difficulty_distribution": {r["difficulty"]: r["cnt"] for r in difficulty_dist},
    }
