"""
Usage:
    python scripts/collect_sessions.py human --count 50
    python scripts/collect_sessions.py bot --count 50
    python scripts/collect_sessions.py bot --type linear --count 20
    python scripts/collect_sessions.py bot --type random --count 20
    python scripts/collect_sessions.py bot --type fast --count 20
    python scripts/collect_sessions.py collect --human 30 --bot 30
    python scripts/collect_sessions.py label --session_id XXX --label human
    python scripts/collect_sessions.py stats
    python scripts/collect_sessions.py export
"""

import argparse
import json
import math
import os
import random
import sys
import time
import uuid

import requests

API = os.environ.get("API_BASE", "http://127.0.0.1:8000")


def _post(path, data):
    r = requests.post(f"{API}{path}", json=data, timeout=15)
    return r.status_code, r.json()


def _get(path):
    r = requests.get(f"{API}{path}", timeout=15)
    return r.status_code, r.json()


def gen_linear_mouse(n=60):
    events = []
    x, y = 100.0, 100.0
    t = 0.0
    for i in range(n):
        dx = random.uniform(5, 25)
        dy = random.uniform(-3, 3)
        x += dx
        y += dy
        t += random.uniform(10, 30)
        events.append({"type": "mousemove", "x": round(x, 1), "y": round(y, 1), "timestamp": round(t, 1)})
    return events


def gen_random_mouse(n=60):
    events = []
    t = 0.0
    for i in range(n):
        x = random.uniform(0, 1920)
        y = random.uniform(0, 1080)
        t += random.uniform(5, 40)
        events.append({"type": "mousemove", "x": round(x, 1), "y": round(y, 1), "timestamp": round(t, 1)})
    return events


def gen_fast_mouse(n=30):
    events = []
    x, y = 50.0, 50.0
    t = 0.0
    for i in range(n):
        x += random.uniform(30, 100)
        y += random.uniform(-10, 10)
        t += random.uniform(1, 5)
        events.append({"type": "mousemove", "x": round(x, 1), "y": round(y, 1), "timestamp": round(t, 1)})
    return events


def gen_human_mouse(n=80):
    events = []
    x, y = 300.0, 400.0
    t = 0.0
    angle = random.uniform(0, 2 * math.pi)
    for i in range(n):
        angle += random.gauss(0, 0.3)
        speed = random.gauss(12, 4)
        speed = max(2, speed)
        dx = speed * math.cos(angle)
        dy = speed * math.sin(angle)
        x += dx + random.gauss(0, 1)
        y += dy + random.gauss(0, 1)
        x = max(0, min(1920, x))
        y = max(0, min(1080, y))
        t += random.gauss(25, 10)
        t = max(t, 0)
        events.append({"type": "mousemove", "x": round(x, 1), "y": round(y, 1), "timestamp": round(t, 1)})
        if random.random() < 0.08:
            t += random.uniform(500, 2000)
            events[-1]["timestamp"] = round(t, 1)
    return events


def gen_human_keyboard(text="বাংলা ক্যাপচা সমাধান"):
    events = []
    t = 0.0
    for ch in text:
        down = t
        hold = random.gauss(80, 25)
        hold = max(30, min(200, hold))
        up = down + hold
        events.append({"key": ch, "keydown": round(down, 1), "keyup": round(up, 1), "duration": round(hold, 1)})
        t = up + random.gauss(60, 20)
        t = max(t, up + 10)
    return events


def gen_bot_keyboard(n=20):
    events = []
    t = 0.0
    for _ in range(n):
        hold = random.uniform(5, 15)
        events.append({"key": "x", "keydown": round(t, 1), "keyup": round(t + hold, 1), "duration": round(hold, 1)})
        t += hold + random.uniform(2, 5)
    return events


def gen_clicks(mouse_events):
    clicks = []
    t = 0.0
    for e in mouse_events:
        t = e.get("timestamp", t)
        if random.random() < 0.05:
            clicks.append({"type": "click", "x": e["x"], "y": e["y"], "button": 0, "timestamp": round(t, 1)})
    return clicks


BOT_PROFILES = {
    "linear": {"mouse_gen": gen_linear_mouse, "kb_gen": gen_bot_keyboard, "mouse_n": 60, "kb_n": 20},
    "random": {"mouse_gen": gen_random_mouse, "kb_gen": gen_bot_keyboard, "mouse_n": 60, "kb_n": 20},
    "fast":   {"mouse_gen": gen_fast_mouse,   "kb_gen": gen_bot_keyboard, "mouse_n": 30, "kb_n": 10},
}


def collect_human(count=1):
    print(f"Collecting {count} human session(s)...")
    for i in range(count):
        mouse = gen_human_mouse(random.randint(60, 120))
        clicks = gen_clicks(mouse)
        mouse = mouse + clicks
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_human_keyboard()

        sid = str(uuid.uuid4())
        status, res = _post("/api/behavior/track", {
            "mouse": mouse,
            "keyboard": keyboard,
            "session_duration_ms": mouse[-1].get("timestamp", 0) if mouse else 0,
        })
        server_sid = res.get("session_id", sid)
        _post("/api/behavior/label", {"session_id": server_sid, "label": "human"})
        print(f"  [{i+1}/{count}] behavior_track: {status}  bot_score={res.get('bot_score', '?')}  labeled=human")

        _generate_and_solve(sid, difficulty=random.choice([1, 2, 3]), human=True)
        time.sleep(0.3)


def collect_bot(count=1, bot_type="linear"):
    profile = BOT_PROFILES.get(bot_type)
    if not profile:
        print(f"Unknown bot type: {bot_type}. Choose from: {list(BOT_PROFILES.keys())}")
        return

    print(f"Collecting {count} bot session(s) [{bot_type}]...")
    for i in range(count):
        mouse = profile["mouse_gen"](profile["mouse_n"])
        clicks = gen_clicks(mouse)
        mouse = mouse + clicks
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = profile["kb_gen"](profile["kb_n"])

        sid = str(uuid.uuid4())
        status, res = _post("/api/behavior/track", {
            "mouse": mouse,
            "keyboard": keyboard,
            "session_duration_ms": mouse[-1].get("timestamp", 0) if mouse else 0,
        })
        server_sid = res.get("session_id", sid)
        _post("/api/behavior/label", {"session_id": server_sid, "label": "bot"})
        print(f"  [{i+1}/{count}] behavior_track: {status}  bot_score={res.get('bot_score', '?')}  labeled=bot")

        _generate_and_solve(sid, difficulty=2, human=False)
        time.sleep(0.3)


def _generate_and_solve(session_id, difficulty=2, human=True):
    status, gen = _post("/api/captcha/generate", {"difficulty": difficulty, "session_id": session_id})
    if status != 200:
        print(f"    captcha generate failed: {status}")
        return

    words = gen.get("words", [])
    if human:
        answer = words
    else:
        answer = [f"ভুল{i}" for i in range(len(words))]

    status, ver = _post("/api/captcha/verify", {
        "session_id": session_id,
        "words": answer,
        "difficulty": difficulty,
        "mouse": [],
        "keyboard": [],
        "solve_time_ms": 3000 if human else 100,
    })
    if status == 200:
        print(f"    captcha verify: correct={ver.get('correct')}  bot_score={ver.get('bot_score', '?')}")
    else:
        print(f"    captcha verify failed: {status}")


def show_stats():
    status, data = _get("/api/dataset/stats")
    if status != 200:
        print(f"Failed to fetch stats: {status}")
        return

    print("=== Dataset Stats ===")
    print(f"  Behavior logs:  {data.get('total_behavior_logs', 0)}")
    print(f"  Human sessions: {data.get('human_sessions', 0)}")
    print(f"  Detected bots:  {data.get('detected_bots', 0)}")
    print(f"  Human labeled:  {data.get('human_labeled', 0)}")
    print(f"  Bot labeled:    {data.get('bot_labeled', 0)}")
    print(f"  Avg bot score:  {data.get('avg_bot_score', 0)}")
    print(f"  RL episodes:    {data.get('total_rl_episodes', 0)}")
    print(f"  Captcha solves: {data.get('total_captcha_sessions', 0)}")
    print(f"  Solve rate:     {data.get('solve_rate', 0)}")


def label_session(session_id, label):
    status, res = _post("/api/behavior/label", {"session_id": session_id, "label": label})
    print(f"Label result: {status}  updated={res.get('updated', 0)}")


def export_dataset():
    status, res = _post("/api/dataset/export", {"format": "json", "scope": "full"})
    if status == 200:
        print(f"Exported to: {res.get('files', {})}")
    else:
        print(f"Export failed: {status} {res}")


def main():
    parser = argparse.ArgumentParser(description="Collect human/bot sessions")
    sub = parser.add_subparsers(dest="command")

    h = sub.add_parser("human")
    h.add_argument("--count", type=int, default=5)

    b = sub.add_parser("bot")
    b.add_argument("--count", type=int, default=5)
    b.add_argument("--type", choices=["linear", "random", "fast"], default="linear")

    c = sub.add_parser("collect")
    c.add_argument("--human", type=int, default=10)
    c.add_argument("--bot", type=int, default=10)
    c.add_argument("--bot-type", choices=["linear", "random", "fast"], default="linear")

    lb = sub.add_parser("label")
    lb.add_argument("--session_id", required=True)
    lb.add_argument("--label", required=True, choices=["human", "bot", "unknown"])

    sub.add_parser("stats")
    sub.add_parser("export")

    args = parser.parse_args()

    if args.command == "human":
        collect_human(args.count)
    elif args.command == "bot":
        collect_bot(args.count, args.type)
    elif args.command == "collect":
        collect_human(args.human)
        collect_bot(args.bot, args.bot_type)
    elif args.command == "label":
        label_session(args.session_id, args.label)
    elif args.command == "stats":
        show_stats()
    elif args.command == "export":
        export_dataset()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
