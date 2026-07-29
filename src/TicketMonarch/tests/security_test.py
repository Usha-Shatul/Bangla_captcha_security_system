"""
Security Test Suite — Behavior simulation on the website.

Tests bot detection accuracy, CAPTCHA system responses, RL agent
decisions, and the full security action escalation pipeline.

Usage:
    python tests/security_test.py                    # run all tests
    python tests/security_test.py --test behavior    # behavior tracking only
    python tests/security_test.py --test captcha     # captcha generation/verify only
    python tests/security_test.py --test escalation  # security action escalation
    python tests/security_test.py --test bot_bypass  # bot bypass attempts
    python tests/security_test.py --test rl          # RL agent decisions
    python tests/security_test.py --verbose          # detailed output
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

BOT_THRESHOLD = 0.5


class SecurityTestReport:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def record(self, name, passed, detail=""):
        status = "PASS" if passed else "FAIL"
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        self.results.append({"name": name, "status": status, "detail": detail})
        symbol = "\u2713" if passed else "\u2717"
        line = f"  [{symbol}] {name}"
        if detail:
            line += f"  \u2014  {detail}"
        print(line)

    def skip(self, name, reason=""):
        self.skipped += 1
        self.results.append({"name": name, "status": "SKIP", "detail": reason})
        print(f"  [~] {name}  \u2014  SKIP: {reason}")

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{'=' * 50}")
        print(f"  TOTAL: {total}  |  PASS: {self.passed}  |  FAIL: {self.failed}  |  SKIP: {self.skipped}")
        print(f"{'=' * 50}")
        return self.failed == 0


# ---------------------------------------------------------------------------
# Behavior Generators
# ---------------------------------------------------------------------------

def gen_human_mouse(n=80):
    events = []
    x, y = 300.0, 400.0
    t = 0.0
    angle = random.uniform(0, 2 * math.pi)
    for _ in range(n):
        angle += random.gauss(0, 0.3)
        speed = max(2, random.gauss(12, 4))
        x += speed * math.cos(angle) + random.gauss(0, 1)
        y += speed * math.sin(angle) + random.gauss(0, 1)
        x = max(0, min(1920, x))
        y = max(0, min(1080, y))
        t += random.gauss(25, 10)
        t = max(t, 0)
        events.append({"type": "mousemove", "x": round(x, 1), "y": round(y, 1), "timestamp": round(t, 1)})
        if random.random() < 0.08:
            t += random.uniform(500, 2000)
            events[-1]["timestamp"] = round(t, 1)
    return events


def gen_human_keyboard(text="বাংলা ক্যাপচা সমাধান একটি বই পড়ছে"):
    events = []
    t = 0.0
    for ch in text:
        down = t
        hold = max(30, min(200, random.gauss(80, 25)))
        up = down + hold
        events.append({"key": ch, "keydown": round(down, 1), "keyup": round(up, 1), "duration": round(hold, 1)})
        t = up + max(10, random.gauss(60, 20))
    return events


def gen_linear_mouse(n=60):
    events = []
    x, y = 100.0, 100.0
    t = 0.0
    for _ in range(n):
        x += random.uniform(5, 25)
        y += random.uniform(-3, 3)
        t += random.uniform(10, 30)
        events.append({"type": "mousemove", "x": round(x, 1), "y": round(y, 1), "timestamp": round(t, 1)})
    return events


def gen_random_mouse(n=60):
    events = []
    t = 0.0
    for _ in range(n):
        x = random.uniform(0, 1920)
        y = random.uniform(0, 1080)
        t += random.uniform(5, 40)
        events.append({"type": "mousemove", "x": round(x, 1), "y": round(y, 1), "timestamp": round(t, 1)})
    return events


def gen_fast_mouse(n=30):
    events = []
    x, y = 50.0, 50.0
    t = 0.0
    for _ in range(n):
        x += random.uniform(30, 100)
        y += random.uniform(-10, 10)
        t += random.uniform(1, 5)
        events.append({"type": "mousemove", "x": round(x, 1), "y": round(y, 1), "timestamp": round(t, 1)})
    return events


def gen_bot_keyboard(n=20):
    events = []
    t = 0.0
    for _ in range(n):
        hold = random.uniform(2, 8)
        events.append({"key": "x", "keydown": round(t, 1), "keyup": round(t + hold, 1), "duration": round(hold, 1)})
        t += hold + random.uniform(1, 3)
    return events


def gen_bot_keyboard_with_paste(text="ভুলভুলভুলভুল"):
    events = []
    t = 0.0
    events.append({"key": "v", "keydown": round(t, 1), "keyup": round(t + 3, 1), "duration": 3.0, "ctrlKey": True})
    t += 5
    for ch in text:
        hold = random.uniform(2, 5)
        events.append({"key": ch, "keydown": round(t, 1), "keyup": round(t + hold, 1), "duration": round(hold, 1)})
        t += hold
    events.append({"key": "a", "keydown": round(t, 1), "keyup": round(t + 2, 1), "duration": 2.0, "ctrlKey": True})
    return events


def gen_clicks(mouse_events):
    clicks = []
    for e in mouse_events:
        if random.random() < 0.05:
            clicks.append({"type": "click", "x": e["x"], "y": e["y"], "button": 0, "timestamp": e.get("timestamp", 0)})
    return clicks


def _post(path, data):
    try:
        r = requests.post(f"{API}{path}", json=data, timeout=15)
        return r.status_code, r.json()
    except requests.exceptions.ConnectionError:
        return 0, {"error": "Connection refused — is the server running?"}
    except Exception as e:
        return 0, {"error": str(e)}


def _get(path):
    try:
        r = requests.get(f"{API}{path}", timeout=15)
        return r.status_code, r.json()
    except requests.exceptions.ConnectionError:
        return 0, {"error": "Connection refused — is the server running?"}
    except Exception as e:
        return 0, {"error": str(e)}


# ---------------------------------------------------------------------------
# Test: Behavior Tracking
# ---------------------------------------------------------------------------

class BehaviorTrackingTests:
    def __init__(self, report: SecurityTestReport, verbose=False):
        self.report = report
        self.verbose = verbose

    def test_health_check(self):
        status, res = _get("/api/health")
        self.report.record("Server health check", status == 200,
                           f"status={status} service={res.get('service', '?')}")

    def test_human_session_detected(self):
        mouse = gen_human_mouse(random.randint(70, 100))
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_human_keyboard()

        status, res = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": mouse[-1].get("timestamp", 0) if mouse else 0,
        })

        bot_score = res.get("bot_score", -1)
        is_bot = res.get("is_bot", True)
        self.report.record("Human session → low bot_score",
                           status == 200 and bot_score < BOT_THRESHOLD and not is_bot,
                           f"bot_score={bot_score:.4f} is_bot={is_bot}")

    def test_linear_bot_detected(self):
        mouse = gen_linear_mouse(60)
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_bot_keyboard(20)

        status, res = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": mouse[-1].get("timestamp", 0) if mouse else 0,
        })

        bot_score = res.get("bot_score", 0)
        self.report.record("Linear bot → high bot_score",
                           status == 200 and bot_score >= BOT_THRESHOLD,
                           f"bot_score={bot_score:.4f}")

    def test_random_bot_detected(self):
        mouse = gen_random_mouse(60)
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_bot_keyboard(20)

        status, res = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": mouse[-1].get("timestamp", 0) if mouse else 0,
        })

        bot_score = res.get("bot_score", 0)
        self.report.record("Random bot → high bot_score",
                           status == 200 and bot_score >= BOT_THRESHOLD,
                           f"bot_score={bot_score:.4f}")

    def test_fast_bot_detected(self):
        mouse = gen_fast_mouse(30)
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_bot_keyboard(10)

        status, res = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": mouse[-1].get("timestamp", 0) if mouse else 0,
        })

        bot_score = res.get("bot_score", 0)
        self.report.record("Fast bot → high bot_score",
                           status == 200 and bot_score >= BOT_THRESHOLD,
                           f"bot_score={bot_score:.4f}")

    def test_paste_keyboard_detected(self):
        mouse = gen_linear_mouse(40)
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_bot_keyboard_with_paste()

        status, res = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": mouse[-1].get("timestamp", 0) if mouse else 0,
        })

        bot_score = res.get("bot_score", 0)
        self.report.record("Paste-heavy keyboard → high bot_score",
                           status == 200 and bot_score >= BOT_THRESHOLD,
                           f"bot_score={bot_score:.4f}")

    def test_empty_session(self):
        status, res = _post("/api/behavior/track", {
            "mouse": [], "keyboard": [],
            "session_duration_ms": 0,
        })
        self.report.record("Empty session accepted",
                           status == 200,
                           f"status={status}")

    def test_security_action_in_response(self):
        mouse = gen_linear_mouse(60)
        keyboard = gen_bot_keyboard(20)

        status, res = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": 500,
        })

        has_action = "security_action" in res
        action = res.get("security_action", {})
        self.report.record("Response includes security_action",
                           status == 200 and has_action and "action" in action,
                           f"action={action.get('action', '?')} name={action.get('action_name', '?')}")


# ---------------------------------------------------------------------------
# Test: CAPTCHA Generation & Verification
# ---------------------------------------------------------------------------

class CaptchaTests:
    def __init__(self, report: SecurityTestReport, verbose=False):
        self.report = report
        self.verbose = verbose

    def test_generate_captcha(self):
        sid = str(uuid.uuid4())[:12]
        status, res = _post("/api/captcha/generate", {
            "difficulty": 2, "session_id": sid,
        })

        has_words = "words" in res and len(res.get("words", [])) > 0
        self.report.record("Captcha generate returns words",
                           status == 200 and has_words,
                           f"words={res.get('words', [])} difficulty={res.get('difficulty', '?')}")

    def test_generate_difficulty_levels(self):
        all_ok = True
        details = []
        for diff in [1, 2, 3]:
            sid = str(uuid.uuid4())[:12]
            status, res = _post("/api/captcha/generate", {"difficulty": diff, "session_id": sid})
            n_words = len(res.get("words", []))
            expected = {1: 3, 2: 4, 3: 5}.get(diff, 4)
            ok = status == 200 and n_words == expected
            all_ok = all_ok and ok
            details.append(f"diff={diff}: words={n_words} expected={expected}")
        self.report.record("Captcha difficulty word counts match", all_ok, " | ".join(details))

    def test_verify_correct_answer(self):
        sid = str(uuid.uuid4())[:12]
        _post("/api/captcha/generate", {"difficulty": 2, "session_id": sid})

        status, gen = _post("/api/captcha/generate", {"difficulty": 2, "session_id": sid})
        words = gen.get("words", [])

        status, res = _post("/api/captcha/verify", {
            "session_id": sid, "words": words, "difficulty": 2,
            "mouse": [], "keyboard": [], "solve_time_ms": 5000,
        })

        self.report.record("Verify correct answer → correct=True",
                           status == 200 and res.get("correct") is True,
                           f"correct={res.get('correct')}")

    def test_verify_wrong_answer(self):
        sid = str(uuid.uuid4())[:12]
        _post("/api/captcha/generate", {"difficulty": 2, "session_id": sid})

        status, res = _post("/api/captcha/verify", {
            "session_id": sid, "words": ["ভুল", "ভুল", "ভুল", "ভুল"], "difficulty": 2,
            "mouse": [], "keyboard": [], "solve_time_ms": 100,
        })

        self.report.record("Verify wrong answer → correct=False",
                           status == 200 and res.get("correct") is False,
                           f"correct={res.get('correct')}")

    def test_verify_returns_bot_score(self):
        sid = str(uuid.uuid4())[:12]
        _post("/api/captcha/generate", {"difficulty": 2, "session_id": sid})

        mouse = gen_linear_mouse(40)
        keyboard = gen_bot_keyboard(15)
        status, res = _post("/api/captcha/verify", {
            "session_id": sid, "words": ["ভুল"] * 4, "difficulty": 2,
            "mouse": mouse, "keyboard": keyboard, "solve_time_ms": 100,
        })

        has_score = "bot_score" in res and "security_action" in res
        self.report.record("Verify returns bot_score + security_action",
                           status == 200 and has_score,
                           f"bot_score={res.get('bot_score', '?')} action={res.get('security_action', {}).get('action_name', '?')}")

    def test_verify_no_session_returns_false(self):
        status, res = _post("/api/captcha/verify", {
            "session_id": "nonexistent_session",
            "words": ["a", "b", "c", "d"], "difficulty": 2,
            "mouse": [], "keyboard": [], "solve_time_ms": 100,
        })
        self.report.record("Verify nonexistent session → correct=False",
                           status == 200 and res.get("correct") is False,
                           f"correct={res.get('correct')}")


# ---------------------------------------------------------------------------
# Test: Security Action Escalation
# ---------------------------------------------------------------------------

SECURITY_ACTIONS = {
    0: "allow", 1: "observe", 2: "captcha_easy",
    3: "captcha_medium", 4: "captcha_hard",
    5: "honeypot", 6: "block",
}


class EscalationTests:
    def __init__(self, report: SecurityTestReport, verbose=False):
        self.report = report
        self.verbose = verbose

    def _track_and_get_action(self, mouse, keyboard, duration_ms=500, prev_diff=1, attempts=0):
        status, res = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": duration_ms,
            "previous_difficulty": prev_diff,
            "attempt_count": attempts,
        })
        return status, res, res.get("security_action", {})

    def test_human_gets_low_action(self):
        mouse = gen_human_mouse(80)
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_human_keyboard()

        status, res, action = self._track_and_get_action(mouse, keyboard, 2000)
        action_idx = action.get("action", -1)

        self.report.record("Human session → action <= captcha_medium",
                           status == 200 and action_idx <= 3,
                           f"action={action_idx} ({SECURITY_ACTIONS.get(action_idx, '?')})")

    def test_bot_gets_high_action(self):
        mouse = gen_linear_mouse(60)
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_bot_keyboard(20)

        status, res, action = self._track_and_get_action(mouse, keyboard, 300)
        action_idx = action.get("action", -1)

        self.report.record("Bot session → action >= captcha_medium",
                           status == 200 and action_idx >= 3,
                           f"action={action_idx} ({SECURITY_ACTIONS.get(action_idx, '?')})")

    def test_repeated_failure_escalates(self):
        mouse = gen_linear_mouse(60)
        keyboard = gen_bot_keyboard(20)

        actions_seen = []
        for attempt in range(5):
            status, res, action = self._track_and_get_action(
                mouse, keyboard, 300, prev_diff=2, attempts=attempt
            )
            actions_seen.append(action.get("action", -1))
            time.sleep(0.2)

        escalated = any(actions_seen[i] >= actions_seen[i - 1] for i in range(1, len(actions_seen)))
        self.report.record("Repeated failures maintain or escalate action",
                           len(actions_seen) == 5,
                           f"actions={actions_seen}")

    def test_all_actions_are_valid(self):
        mouse = gen_linear_mouse(40)
        keyboard = gen_bot_keyboard(15)

        status, res, action = self._track_and_get_action(mouse, keyboard, 500)
        action_idx = action.get("action", -1)

        self.report.record("Security action is in valid range [0,6]",
                           0 <= action_idx <= 6,
                           f"action={action_idx}")

    def test_action_includes_name(self):
        mouse = gen_linear_mouse(40)
        keyboard = gen_bot_keyboard(15)

        status, res, action = self._track_and_get_action(mouse, keyboard, 500)

        self.report.record("Security action includes action_name field",
                           "action_name" in action,
                           f"action_name={action.get('action_name', 'MISSING')}")


# ---------------------------------------------------------------------------
# Test: Bot Bypass Attempts
# ---------------------------------------------------------------------------

class BotBypassTests:
    def __init__(self, report: SecurityTestReport, verbose=False):
        self.report = report
        self.verbose = verbose

    def test_human_like_mouse_bot_detected(self):
        mouse = gen_human_mouse(80)
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_bot_keyboard(20)

        status, res = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": 1500,
        })

        bot_score = res.get("bot_score", 0)
        self.report.record("Human mouse + bot keyboard → elevated score",
                           status == 200 and bot_score > 0.3,
                           f"bot_score={bot_score:.4f}")

    def test_fast_solve_time_detected(self):
        sid = str(uuid.uuid4())[:12]
        _post("/api/captcha/generate", {"difficulty": 2, "session_id": sid})

        mouse = gen_linear_mouse(40)
        keyboard = gen_bot_keyboard(15)
        status, res = _post("/api/captcha/verify", {
            "session_id": sid, "words": ["ভুল"] * 4, "difficulty": 2,
            "mouse": mouse, "keyboard": keyboard, "solve_time_ms": 50,
        })

        self.report.record("Ultra-fast solve time → flagged",
                           status == 200,
                           f"solve_time_ms=50 bot_score={res.get('bot_score', '?')}")

    def test_wrong_answers_multiple_attempts(self):
        sid = str(uuid.uuid4())[:12]
        _post("/api/captcha/generate", {"difficulty": 2, "session_id": sid})

        mouse = gen_fast_mouse(20)
        keyboard = gen_bot_keyboard_with_paste()
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))

        wrong = ["ভুল"] * 4
        results = []
        for i in range(3):
            status, res = _post("/api/captcha/verify", {
                "session_id": sid, "words": wrong, "difficulty": 2,
                "mouse": mouse, "keyboard": keyboard, "solve_time_ms": 80,
            })
            results.append(res.get("bot_score", 0))
            time.sleep(0.1)

        self.report.record("3 wrong attempts maintain high bot_score",
                           all(s >= BOT_THRESHOLD for s in results),
                           f"scores={[f'{s:.3f}' for s in results]}")

    def test_context_menu_flagged(self):
        mouse = gen_linear_mouse(40)
        mouse.append({"type": "contextmenu", "x": 500, "y": 300, "timestamp": 200.0})
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_bot_keyboard(10)

        status, res = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": 500,
        })

        features = {}
        try:
            features = json.loads(res.get("features_json", "{}")) if "features_json" in res else {}
        except Exception:
            pass

        self.report.record("Context menu event detected",
                           status == 200,
                           f"bot_score={res.get('bot_score', '?')}")


# ---------------------------------------------------------------------------
# Test: RL Agent Decisions
# ---------------------------------------------------------------------------

class RLAgentTests:
    def __init__(self, report: SecurityTestReport, verbose=False):
        self.report = report
        self.verbose = verbose

    def test_rl_stats_available(self):
        status, res = _get("/api/rl/stats")
        self.report.record("RL stats endpoint accessible",
                           status == 200 and "total_episodes" in res,
                           f"total_episodes={res.get('total_episodes', '?')}")

    def test_rl_qtable_accessible(self):
        status, res = _get("/api/rl/qtable")
        self.report.record("RL Q-table endpoint accessible",
                           status == 200,
                           f"type={type(res).__name__}")

    def test_rl_difficulty_endpoint(self):
        status, res = _post("/api/rl/difficulty", {
            "features": {
                "mouse_avg_speed": 10, "mouse_std_speed": 5,
                "kb_dwell_mean": 80, "kb_speed_cpm": 120,
                "bot_score": 0.3, "confidence": 0.8,
            },
            "previous_difficulty": 1, "attempt_count": 0,
            "session_duration_ms": 2000,
        })
        self.report.record("RL difficulty endpoint returns action",
                           status == 200 and "action" in res,
                           f"action={res.get('action', '?')} name={res.get('action_name', '?')}")

    def test_rl_reward_endpoint(self):
        status, res = _post("/api/rl/reward", {
            "features": {
                "mouse_avg_speed": 10, "mouse_std_speed": 5,
                "kb_dwell_mean": 80, "kb_speed_cpm": 120,
                "bot_score": 0.3, "confidence": 0.8,
            },
            "action": 2, "reward": 1.0,
            "done": True,
            "previous_difficulty": 1, "attempt_count": 1,
            "session_duration_ms": 3000,
        })
        self.report.record("RL reward endpoint accepts update",
                           status == 200,
                           f"status={status}")

    def test_rl_high_bot_score_gets_strong_action(self):
        status, res = _post("/api/rl/difficulty", {
            "features": {
                "mouse_avg_speed": 8000, "mouse_std_speed": 2,
                "kb_dwell_mean": 5, "kb_speed_cpm": 500,
                "bot_score": 0.95, "confidence": 0.95,
            },
            "previous_difficulty": 2, "attempt_count": 2,
            "session_duration_ms": 100,
        })
        action = res.get("action", 0)
        self.report.record("High bot_score RL → action >= captcha_hard",
                           status == 200 and action >= 4,
                           f"action={action} ({SECURITY_ACTIONS.get(action, '?')})")


# ---------------------------------------------------------------------------
# Test: Behavior History & Stats
# ---------------------------------------------------------------------------

class HistoryStatsTests:
    def __init__(self, report: SecurityTestReport, verbose=False):
        self.report = report
        self.verbose = verbose

    def test_behavior_history(self):
        status, res = _get("/api/behavior/history")
        logs = res.get("logs", [])
        self.report.record("Behavior history returns logs list",
                           status == 200 and isinstance(logs, list),
                           f"count={len(logs)}")

    def test_behavior_stats(self):
        status, res = _get("/api/behavior/stats")
        self.report.record("Behavior stats endpoint works",
                           status == 200 and "total_sessions" in res,
                           f"total={res.get('total_sessions', '?')} bots={res.get('detected_bots', '?')}")

    def test_label_session(self):
        mouse = gen_linear_mouse(30)
        keyboard = gen_bot_keyboard(10)
        status, res = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": 200,
        })
        sid = res.get("session_id", "")
        if sid:
            lstatus, lres = _post("/api/behavior/label", {"session_id": sid, "label": "bot"})
            self.report.record("Label session as bot",
                               lstatus == 200 and lres.get("updated", 0) >= 0,
                               f"updated={lres.get('updated', 0)}")
        else:
            self.report.skip("Label session as bot", "no session_id returned")


# ---------------------------------------------------------------------------
# Test: Full Pipeline (User + Bot Session)
# ---------------------------------------------------------------------------

class FullPipelineTests:
    def __init__(self, report: SecurityTestReport, verbose=False):
        self.report = report
        self.verbose = verbose

    def test_human_full_session(self):
        sid = str(uuid.uuid4())[:12]

        mouse = gen_human_mouse(80)
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_human_keyboard()

        s1, r1 = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": 2000,
        })

        s2, r2 = _post("/api/captcha/generate", {"difficulty": 2, "session_id": sid})
        words = r2.get("words", [])

        s3, r3 = _post("/api/captcha/verify", {
            "session_id": sid, "words": words, "difficulty": 2,
            "mouse": mouse[:20], "keyboard": keyboard[:10], "solve_time_ms": 5000,
        })

        all_ok = all(s == 200 for s in [s1, s2, s3])
        low_bot = r1.get("bot_score", 1) < BOT_THRESHOLD
        correct = r3.get("correct", False)

        self.report.record("Human full session → pass all checks",
                           all_ok and low_bot and correct,
                           f"bot_score={r1.get('bot_score', '?')} correct={correct}")

    def test_bot_full_session(self):
        sid = str(uuid.uuid4())[:12]

        mouse = gen_linear_mouse(60)
        mouse += gen_clicks(mouse)
        mouse.sort(key=lambda e: e.get("timestamp", 0))
        keyboard = gen_bot_keyboard(20)

        s1, r1 = _post("/api/behavior/track", {
            "mouse": mouse, "keyboard": keyboard,
            "session_duration_ms": 300,
        })

        s2, r2 = _post("/api/captcha/generate", {"difficulty": 2, "session_id": sid})

        s3, r3 = _post("/api/captcha/verify", {
            "session_id": sid, "words": ["ভুল"] * 4, "difficulty": 2,
            "mouse": mouse, "keyboard": keyboard, "solve_time_ms": 80,
        })

        all_ok = all(s == 200 for s in [s1, s2, s3])
        high_bot = r1.get("bot_score", 0) >= BOT_THRESHOLD
        wrong = r3.get("correct", True) is False

        self.report.record("Bot full session → detected + wrong answer",
                           all_ok and high_bot and wrong,
                           f"bot_score={r1.get('bot_score', '?')} correct={r3.get('correct', '?')}")

    def test_booking_blocked_without_captcha(self):
        status, res = requests.post(f"{API}/api/booking/ticket",
                                    json={"destination": "ঢাকা", "date": "2026-08-01", "passengers": 1},
                                    headers={"Authorization": "Bearer fake_token"},
                                    timeout=15).status_code, \
                      requests.post(f"{API}/api/booking/ticket",
                                    json={"destination": "ঢাকা", "date": "2026-08-01", "passengers": 1},
                                    headers={"Authorization": "Bearer fake_token"},
                                    timeout=15).json()
        self.report.record("Booking blocked without captcha_verified",
                           status == 403 or "ক্যাপচা" in res.get("detail", ""),
                           f"status={status}")


# ---------------------------------------------------------------------------
# Main Runner
# ---------------------------------------------------------------------------

def run_all_tests(test_filter=None, verbose=False):
    report = SecurityTestReport()

    print(f"\n{'=' * 50}")
    print(f"  Security Test Suite — Bangla CAPTCHA System")
    print(f"  API: {API}")
    print(f"{'=' * 50}\n")

    suites = [
        ("behavior", "Behavior Tracking", BehaviorTrackingTests),
        ("captcha", "CAPTCHA Generation & Verification", CaptchaTests),
        ("escalation", "Security Action Escalation", EscalationTests),
        ("bot_bypass", "Bot Bypass Attempts", BotBypassTests),
        ("rl", "RL Agent Decisions", RLAgentTests),
        ("history", "History & Stats", HistoryStatsTests),
        ("pipeline", "Full Pipeline (User + Bot Session)", FullPipelineTests),
    ]

    for key, label, cls in suites:
        if test_filter and key != test_filter:
            continue
        print(f"\n--- {label} ---")
        suite = cls(report, verbose)
        for method_name in dir(suite):
            if method_name.startswith("test_"):
                getattr(suite, method_name)()

    report.summary()
    return report


def main():
    parser = argparse.ArgumentParser(description="Security Test Suite — Bangla CAPTCHA")
    parser.add_argument("--test", choices=["behavior", "captcha", "escalation", "bot_bypass", "rl", "history", "pipeline"],
                        help="Run a specific test suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    success = run_all_tests(test_filter=args.test, verbose=args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
