"""
Stealth Bot — Simulates a realistic checkout flow with human-like patterns.

Generates multiple track calls per session: page browse, form fill, submit.
Mouse paths use smooth curves; keyboard has realistic dwell/flight variation.

Usage:
    python bots/stealth_bot.py --url http://localhost:5000
"""

import os
import sys
import json
import time
import random
import math
import argparse
import requests


def _bezier(x0, y0, x1, y1, steps):
    cx = random.uniform(min(x0, x1) - 50, max(x0, x1) + 50)
    cy = random.uniform(min(y0, y1) - 50, max(y0, y1) + 50)
    pts = []
    for i in range(steps):
        t = i / max(steps - 1, 1)
        u = 1 - t
        x = u * u * x0 + 2 * u * t * cx + t * t * x1
        y = u * u * y0 + 2 * u * t * cy + t * t * y1
        pts.append((round(x, 1), round(y, 1)))
    return pts


def _type_text(text, t_start, errors=None):
    events = []
    t = t_start
    for ch in text:
        if errors and random.random() < 0.05:
            wrong = chr(random.randint(97, 122))
            t += random.uniform(40, 100)
            events.append({"type": "keydown", "key": wrong, "code": f"Key{wrong.upper()}", "timestamp": round(t, 1)})
            t += random.uniform(25, 60)
            events.append({"type": "keyup", "key": wrong, "code": f"Key{wrong.upper()}", "timestamp": round(t, 1)})
            t += random.uniform(80, 200)
            events.append({"type": "keydown", "key": "Backspace", "code": "Backspace", "timestamp": round(t, 1)})
            t += random.uniform(20, 50)
            events.append({"type": "keyup", "key": "Backspace", "code": "Backspace", "timestamp": round(t, 1)})
            t += random.uniform(40, 100)

        t += random.gauss(95, 35)
        t = max(t_start, t)
        code = f"Key{ch.upper()}" if ch.isalpha() else ch
        events.append({"type": "keydown", "key": ch, "code": code, "timestamp": round(t, 1)})
        t += random.gauss(65, 20)
        t = max(t + 1, t)
        events.append({"type": "keyup", "key": ch, "code": code, "timestamp": round(t, 1)})
    return events, t


def _generate_checkout_phases():
    all_mouse = []
    all_keyboard = []
    t = 0.0
    x, y = random.uniform(400, 900), random.uniform(200, 400)

    for _ in range(random.randint(6, 12)):
        t += random.uniform(100, 300)
        nx = x + random.gauss(0, 120)
        ny = y + random.gauss(0, 80)
        nx = max(50, min(1870, nx))
        ny = max(50, min(1030, ny))
        steps = random.randint(4, 8)
        for px, py in _bezier(x, y, nx, ny, steps):
            t += random.uniform(20, 50)
            all_mouse.append({
                "x": px, "y": py, "timestamp": round(t, 1),
                "button": 0, "click_type": "",
                "speed": round(random.uniform(200, 700), 1),
            })
        if random.random() < 0.15:
            all_mouse[-1]["click_type"] = "click"
        x, y = nx, ny

    t += random.uniform(200, 500)
    ke, t = _type_text("rahata hossein", t, errors=True)
    all_keyboard.extend(ke)

    t += random.uniform(300, 600)
    ke, t = _type_text("rahata@example.com", t)
    all_keyboard.extend(ke)

    t += random.uniform(200, 400)
    ke, t = _type_text("01712345678", t)
    all_keyboard.extend(ke)

    return all_mouse, all_keyboard, round(t, 1)


def run_stealth_bot(base_url: str, n_sessions: int = 10):
    print(f"Running stealth bot against {base_url} ({n_sessions} sessions)")

    detected = 0
    for i in range(n_sessions):
        print(f"\n--- Session {i + 1}/{n_sessions} ---")

        mouse_events, keyboard_events, duration = _generate_checkout_phases()

        try:
            resp = requests.post(
                f"{base_url}/api/behavior/track",
                json={
                    "mouse": mouse_events,
                    "keyboard": keyboard_events,
                    "session_duration_ms": duration,
                    "previous_difficulty": 1,
                    "attempt_count": 0,
                },
                timeout=10,
            )
            data = resp.json()
            is_bot = data.get("is_bot", False)
            score = data.get("bot_score", 0)
            action = data.get("security_action", {}).get("action_name", "?")

            if is_bot:
                detected += 1

            print(f"  Events: mouse={len(mouse_events)} kb={len(keyboard_events)} dur={duration:.0f}ms")
            print(f"  Score: {score:.3f} | Bot: {is_bot} | Action: {action}")
        except Exception as e:
            print(f"  Error: {e}")

        time.sleep(random.uniform(1.5, 3.5))

    print(f"\n{'=' * 50}")
    print(f"Stealth bot complete: {n_sessions} sessions")
    print(f"Detected: {detected}/{n_sessions} ({detected/n_sessions:.0%})")


def main():
    parser = argparse.ArgumentParser(description="Stealth bot for testing")
    parser.add_argument("--url", default="http://localhost:5000", help="Backend URL")
    parser.add_argument("--sessions", type=int, default=10, help="Number of sessions")
    args = parser.parse_args()

    run_stealth_bot(args.url, args.sessions)


if __name__ == "__main__":
    main()
