"""
Simple Browser Bot — Simulates a basic checkout flow.

Generates sessions that resemble a real checkout: multiple behavior
track calls, form-like typing, and page-navigation mouse movements.

Usage:
    python bots/browser_bot.py --url http://localhost:5000
"""

import os
import sys
import json
import time
import random
import math
import argparse
import requests


def _smooth_path(x0, y0, x1, y1, steps):
    """Generate a curved path between two points."""
    points = []
    cx = random.uniform(min(x0, x1), max(x0, x1))
    cy = random.uniform(min(y0, y1), max(y0, y1))
    for i in range(steps):
        t = i / max(steps - 1, 1)
        u = 1 - t
        x = u * u * x0 + 2 * u * t * cx + t * t * x1
        y = u * u * y0 + 2 * u * t * cy + t * t * y1
        points.append((x, y))
    return points


def _generate_checkout_events():
    """Generate events mimicking a checkout page visit."""
    mouse = []
    keyboard = []
    t = 0.0

    x, y = random.uniform(200, 500), random.uniform(100, 300)
    for _ in range(random.randint(8, 18)):
        t += random.uniform(80, 250)
        nx = x + random.gauss(0, 80)
        ny = y + random.gauss(0, 60)
        nx = max(50, min(1870, nx))
        ny = max(50, min(1030, ny))
        path = _smooth_path(x, y, nx, ny, random.randint(3, 6))
        for px, py in path:
            t += random.uniform(15, 40)
            mouse.append({
                "x": round(px, 1), "y": round(py, 1),
                "timestamp": round(t, 1), "button": 0,
                "click_type": "", "speed": round(random.uniform(150, 600), 1),
            })
        if random.random() < 0.2:
            mouse[-1]["click_type"] = "click"
            mouse[-1]["button"] = 0
        x, y = nx, ny

    name = "rahata"
    t += random.uniform(300, 600)
    for ch in name:
        t += random.uniform(60, 160)
        keyboard.append({"type": "keydown", "key": ch, "code": f"Key{ch.upper()}", "timestamp": round(t, 1)})
        t += random.uniform(30, 90)
        keyboard.append({"type": "keyup", "key": ch, "code": f"Key{ch.upper()}", "timestamp": round(t, 1)})

    email = "user@test.com"
    t += random.uniform(200, 400)
    for ch in email:
        t += random.uniform(40, 120)
        keyboard.append({"type": "keydown", "key": ch, "code": f"Key{ch.upper()}" if ch.isalpha() else ch, "timestamp": round(t, 1)})
        t += random.uniform(25, 70)
        keyboard.append({"type": "keyup", "key": ch, "code": f"Key{ch.upper()}" if ch.isalpha() else ch, "timestamp": round(t, 1)})

    return mouse, keyboard, round(t, 1)


def run_http_bot(base_url: str, n_sessions: int = 5):
    """Simulate bot sessions using raw HTTP requests."""
    print(f"Running HTTP bot against {base_url} ({n_sessions} sessions)")

    for i in range(n_sessions):
        print(f"\n--- Session {i + 1}/{n_sessions} ---")

        mouse_events, keyboard_events, duration = _generate_checkout_events()

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
            print(f"  Events:    mouse={len(mouse_events)} keyboard={len(keyboard_events)}")
            print(f"  Bot score: {data.get('bot_score', '?'):.3f}")
            print(f"  Is bot:    {data.get('is_bot', '?')}")
            print(f"  Action:    {data.get('security_action', {}).get('action_name', '?')}")
        except Exception as e:
            print(f"  Error: {e}")

        time.sleep(random.uniform(1.0, 2.5))

    print(f"\nBot run complete: {n_sessions} sessions")


def main():
    parser = argparse.ArgumentParser(description="Simple HTTP bot for testing")
    parser.add_argument("--url", default="http://localhost:5000", help="Backend URL")
    parser.add_argument("--sessions", type=int, default=5, help="Number of sessions")
    args = parser.parse_args()

    run_http_bot(args.url, args.sessions)


if __name__ == "__main__":
    main()
