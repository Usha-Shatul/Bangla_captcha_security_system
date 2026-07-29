"""
LLM Bot — Uses an LLM to generate human-like behavioral telemetry.

Requires: pip install langchain-anthropic playwright install chromium

This bot uses an LLM to generate realistic mouse/keyboard event sequences
that attempt to mimic human behavior patterns, making it a more
sophisticated adversary for the CAPTCHA system.

Usage:
    python bots/llm_bot.py --url http://localhost:5000 --api-key YOUR_ANTHROPIC_KEY
"""

import os
import sys
import json
import time
import random
import argparse
import requests


def generate_with_llm(api_key: str, prompt: str) -> str:
    """Generate text using Anthropic's Claude via langchain."""
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage

        llm = ChatAnthropic(
            model="claude-3-haiku-20240307",
            anthropic_api_key=api_key,
            temperature=0.8,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except ImportError:
        print("WARNING: langchain-anthropic not installed. Using fallback.")
        return None
    except Exception as e:
        print(f"WARNING: LLM call failed: {e}. Using fallback.")
        return None


def parse_events_from_llm(text: str) -> dict:
    """Parse mouse/keyboard events from LLM output."""
    try:
        # Try to find JSON in the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass

    # Fallback: generate basic events
    return {
        "mouse_events": [
            {
                "x": random.uniform(100, 1800),
                "y": random.uniform(100, 900),
                "timestamp": float(i * random.exponential(30)),
                "button": 0,
                "click_type": "click" if random.random() < 0.1 else "",
                "speed": float(max(0, random.gauss(500, 200))),
            }
            for i in range(random.randint(30, 80))
        ],
        "keyboard_events": [],
    }


def run_llm_bot(base_url: str, api_key: str, n_sessions: int = 5):
    """Run LLM-powered bot sessions."""
    print(f"Running LLM bot against {base_url} ({n_sessions} sessions)")

    prompt_template = """Generate a JSON object with realistic browser behavioral telemetry for a CAPTCHA-solving session.

The JSON should have:
- "mouse_events": array of {x, y, timestamp, button, click_type, speed} with 30-80 events showing natural mouse movement (curves, pauses, varying speed)
- "keyboard_events": array of {type, key, code, timestamp} with 10-40 keystroke events showing human typing patterns (varying dwell times 40-120ms, flight times 60-200ms)

Return ONLY the JSON object, no explanation."""

    for i in range(n_sessions):
        print(f"\n--- Session {i + 1}/{n_sessions} ---")

        if api_key:
            llm_output = generate_with_llm(api_key, prompt_template)
            events = parse_events_from_llm(llm_output) if llm_output else {}
        else:
            events = {}

        if not events.get("mouse_events"):
            # Fallback to generated events
            events = {
                "mouse_events": [
                    {
                        "x": random.uniform(100, 1800),
                        "y": random.uniform(100, 900),
                        "timestamp": float(j * random.exponential(25)),
                        "button": 0,
                        "click_type": "click" if random.random() < 0.1 else "",
                        "speed": float(max(0, random.gauss(450, 180))),
                    }
                    for j in range(random.randint(35, 70))
                ],
                "keyboard_events": [],
            }

            t = 0.0
            for j in range(random.randint(10, 25)):
                t += random.uniform(50, 180)
                key = chr(random.randint(97, 123))
                events["keyboard_events"].append({
                    "type": "keydown", "key": key,
                    "code": f"Key{key.upper()}", "timestamp": round(t, 1),
                })
                t += random.uniform(30, 100)
                events["keyboard_events"].append({
                    "type": "keyup", "key": key,
                    "code": f"Key{key.upper()}", "timestamp": round(t, 1),
                })

        try:
            resp = requests.post(
                f"{base_url}/api/behavior/track",
                json={
                    "mouse": events.get("mouse_events", []),
                    "keyboard": events.get("keyboard_events", []),
                    "session_duration_ms": 8000,
                },
                timeout=10,
            )
            data = resp.json()
            print(f"  Score: {data.get('bot_score', 0):.3f} | "
                  f"Bot: {data.get('is_bot', '?')} | "
                  f"Action: {data.get('security_action', {}).get('action_name', '?')}")
        except Exception as e:
            print(f"  Error: {e}")

        time.sleep(random.uniform(1, 3))

    print(f"\nLLM bot complete: {n_sessions} sessions")


def main():
    parser = argparse.ArgumentParser(description="LLM-powered bot for testing")
    parser.add_argument("--url", default="http://localhost:5000", help="Backend URL")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY", ""),
                        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--sessions", type=int, default=5, help="Number of sessions")
    args = parser.parse_args()

    run_llm_bot(args.url, args.api_key, args.sessions)


if __name__ == "__main__":
    main()
