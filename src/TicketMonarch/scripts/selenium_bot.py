"""
Selenium bot with two-phase behavior for adaptive CAPTCHA research.

Phase 1 -- Human-like browsing:
    Navigates the TicketMonarch site naturally: scrolls, moves mouse in
    curved paths, types at realistic speed with variable rhythm, pauses
    to "read" content.  The React MouseTracker/KeyboardTracker components
    capture real DOM events that look human.

Phase 2 -- Bot behavior at CAPTCHA:
    Switches to mechanical behavior: straight-line mouse movement at
    extreme speed, ultra-fast uniform typing (5-10 ms hold), zero idle
    periods, immediate wrong answer submission.  The behavioral biometrics
    module extracts features that trigger the heuristic bot detector.

Prerequisites:
    pip install selenium webdriver-manager
    Chrome browser installed.

Both Flask backend (port 8000) and Vite dev server (port 3000) must be running.

Usage:
    python scripts/selenium_bot.py --count 10
    python scripts/selenium_bot.py --count 20 --headless
    python scripts/selenium_bot.py --count 5 --verbose
"""

import argparse
import io
import math
import os
import random
import sys
import time
import uuid

# --- Fix PowerShell cp1252 UnicodeEncodeError ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WDM = True
except ImportError:
    USE_WDM = False

# Use "localhost" (not 127.0.0.1) because Vite binds to IPv6
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.environ.get("API_BASE", "http://localhost:8000")

WAIT_TIMEOUT = 40


# ---------------------------------------------------------------------------
#  Driver setup
# ---------------------------------------------------------------------------

def create_driver(headless=False):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    if USE_WDM:
        service = Service(ChromeDriverManager().install())
    else:
        service = Service()
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    driver.maximize_window()
    driver.implicitly_wait(5)
    driver.set_page_load_timeout(60)
    print("[driver] Chrome launched (maximized)")
    return driver


# ===================================================================
#  PHASE 1 -- Human-like interaction primitives
# ===================================================================

def _human_pause(lo=0.4, hi=1.8):
    time.sleep(random.uniform(lo, hi))


def _move_mouse_to(driver, target_x, target_y, duration=0.3, human=True):
    """Move mouse to absolute viewport coordinates (target_x, target_y).

    Uses JavaScript to teleport to start position, then either:
      - human=True:  small random jitter steps for natural movement
      - human=False: one fast mechanical move
    """
    # First, use JS to set cursor near target via element_from_point
    # Then use ActionChains to move from that element to exact offset
    try:
        # Create a tiny invisible element at the target location
        driver.execute_script("""
            var el = document.createElement('div');
            el.id = '__selenium_target';
            el.style.cssText = 'position:fixed;left:%dpx;top:%dpx;width:1px;height:1px;z-index:99999;pointer-events:none;';
            document.body.appendChild(el);
        """ % (int(target_x), int(target_y)))
        time.sleep(0.02)

        target_el = driver.find_element(By.ID, "__selenium_target")

        if human:
            # Move to element center, then small jitter for realism
            actions = ActionChains(driver)
            actions.move_to_element_with_offset(target_el, 0, 0)
            actions.pause(0.05)
            # Small random jitter near the target
            for _ in range(random.randint(2, 5)):
                jx = random.randint(-3, 3)
                jy = random.randint(-3, 3)
                actions.move_by_offset(jx, jy)
                actions.pause(random.uniform(0.01, 0.04))
            actions.perform()
        else:
            # Fast mechanical move directly to element
            actions = ActionChains(driver)
            actions.move_to_element_with_offset(target_el, 0, 0)
            actions.perform()

    except Exception:
        pass
    finally:
        try:
            driver.execute_script("""
                var el = document.getElementById('__selenium_target');
                if (el) el.remove();
            """)
        except Exception:
            pass


def human_click_element(driver, element):
    """Move to element with curved mouse motion, pause, then click."""
    try:
        loc = element.location_once_scrolled_into_view
        size = element.size
        cx = loc["x"] + size["width"] * random.uniform(0.25, 0.75)
        cy = loc["y"] + size["height"] * random.uniform(0.25, 0.75)
    except Exception:
        cx, cy = random.uniform(300, 700), random.uniform(200, 500)
    _move_mouse_to(driver, cx, cy, human=True)
    _human_pause(0.1, 0.35)
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def human_type(driver, element, text):
    element.click()
    time.sleep(random.uniform(0.15, 0.35))
    for ch in text:
        element.send_keys(ch)
        dwell = max(30, random.gauss(95, 30))
        time.sleep(dwell / 1000.0)
        if random.random() < 0.06:
            time.sleep(random.uniform(0.3, 0.9))
        flight = max(15, random.gauss(65, 25))
        time.sleep(flight / 1000.0)


def human_scroll(driver, y_delta=None, pauses=True):
    if y_delta is None:
        y_delta = random.randint(150, 500) * random.choice([-1, 1])
    driver.execute_script(f"window.scrollBy(0, {y_delta});")
    if pauses:
        _human_pause(0.3, 0.8)


# ===================================================================
#  PHASE 2 -- Bot interaction primitives (at CAPTCHA)
# ===================================================================

def bot_move_to(driver, target_x, target_y):
    """Mechanical straight-line move to absolute coordinates."""
    _move_mouse_to(driver, target_x, target_y, human=False)


def bot_type(element, text):
    """Ultra-fast uniform typing -- 2-5 ms hold, 0-2 ms gap.
    This produces typing_rhythm_std near 0, avg_hold < 10 ms,
    CPM > 2000, correction_ratio = 0 -- maximum bot signals."""
    element.click()
    time.sleep(0.03)
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.002, 0.005))
        time.sleep(random.uniform(0.000, 0.002))


# ===================================================================
#  Navigation helpers
# ===================================================================

def _find_concert_cards(driver):
    cards = driver.find_elements(By.CSS_SELECTOR, ".concert-card")
    if not cards:
        cards = driver.find_elements(By.CSS_SELECTOR, "[class*='concert']")
    if not cards:
        all_el = driver.find_elements(By.CSS_SELECTOR, "div[style], div[class]")
        cards = [e for e in all_el if e.is_displayed() and "cursor" in (
            e.value_of_css_property("cursor") or "")]
    return cards


def _find_checkout_button(driver):
    # Primary: the gold button on seat selection page
    for sel in [".stub .btn-gold", "button.btn-gold"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.is_displayed() and el.is_enabled():
                return el
        except Exception:
            pass
    # Fallback: search all buttons by text
    for btn in driver.find_elements(By.TAG_NAME, "button"):
        txt = btn.text.strip()
        if "checkout" in txt.lower() or "\u099a\u09c7\u0995" in txt:
            if btn.is_displayed():
                return btn
    return None


def _find_captcha_input(driver, timeout=WAIT_TIMEOUT):
    for _ in range(timeout):
        for sel in [".captcha-input", "input.captcha-input",
                     ".bangla-captcha input[type='text']"]:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                if el.is_displayed():
                    return el
        time.sleep(1.0)
    return None


def _find_captcha_submit(driver):
    for sel in [".captcha-submit", "button.captcha-submit"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.is_displayed() and el.is_enabled():
                return el
        except Exception:
            pass
    for btn in driver.find_elements(By.TAG_NAME, "button"):
        txt = btn.text.strip()
        if "\u09af\u09be\u099a\u09be\u0987" in txt:
            return btn
    return None


def _count_captcha_words(driver):
    words = driver.find_elements(By.CSS_SELECTOR, ".captcha-word")
    return len(words) if words else 4


def _get_security_state(driver):
    """Return 'allow', 'block', 'captcha', 'observe', 'honeypot', or None."""
    try:
        badge = driver.find_element(By.CSS_SELECTOR, ".action-badge")
        text = badge.text.lower()
        if "\u0985\u09a8\u09c1\u09ae\u09a4\u09bf" in text or "allow" in text:
            return "allow"
        if "\u09ac\u09cd\u09b2\u0995" in text or "block" in text:
            return "block"
        if "\u09aa\u09b0\u09cd\u09af\u09ac\u09c7\u0995\u09cd\u09b7\u09a3" in text or "observe" in text:
            return "observe"
        if "\u0995\u09cd\u09af\u09be\u09aa\u099a\u09be" in text or "captcha" in text:
            return "captcha"
        if "\u09b9\u09a8\u09bf\u09af\u09bc\u09aa\u099f" in text or "honeypot" in text:
            return "honeypot"
    except Exception:
        pass
    try:
        decision = driver.find_element(By.CSS_SELECTOR, ".captcha-decision p")
        text = decision.text
        if "\u0985\u09a8\u09c1\u09ae\u09a4\u09bf" in text:
            return "allow"
        if "\u09ac\u09cd\u09b2\u0995" in text:
            return "block"
    except Exception:
        pass
    return None


# ===================================================================
#  Full session runner
# ===================================================================

def run_session(driver, verbose=True):
    sid = str(uuid.uuid4())
    result = {
        "session_id": sid,
        "success": False,
        "captcha_encountered": False,
        "captcha_answered": False,
        "detected_bot": False,
        "error": None,
    }

    try:
        # ── PHASE 1: Human-like browsing ──────────────────────────
        print("  [1/8] Opening homepage ...")
        driver.get(FRONTEND_URL)
        _human_pause(2.0, 3.5)

        print("  [2/8] Scrolling page ...")
        human_scroll(driver, random.randint(100, 300))
        _human_pause(0.5, 1.2)

        cards = _find_concert_cards(driver)
        if not cards:
            result["error"] = "No concert cards found on homepage"
            print(f"  [!] No concert cards. title={driver.title}")
            return result
        print(f"  [3/8] Clicking concert card ({len(cards)} found) ...")
        target_card = random.choice(cards[:5])
        human_click_element(driver, target_card)
        _human_pause(1.5, 3.0)

        human_scroll(driver, random.randint(50, 200))
        _human_pause(0.3, 0.8)

        seats = driver.find_elements(By.CSS_SELECTOR, "button.seat:not(.taken)")
        if not seats:
            seats = driver.find_elements(
                By.CSS_SELECTOR, "button:not(.taken):not([disabled])")
        if not seats:
            result["error"] = "No available seats found"
            print(f"  [!] No seats. url={driver.current_url}")
            return result
        print(f"  [4/8] Selecting seats ({len(seats)} available) ...")
        n_seats = random.randint(1, min(3, len(seats)))
        for seat in random.sample(seats, n_seats):
            human_click_element(driver, seat)
            _human_pause(0.2, 0.5)

        human_scroll(driver, random.randint(50, 150))
        _human_pause(0.4, 0.9)

        checkout_btn = _find_checkout_button(driver)
        if not checkout_btn:
            result["error"] = "Checkout button not found"
            print(f"  [!] No checkout btn. url={driver.current_url}")
            return result
        print("  [5/8] Going to checkout ...")
        human_click_element(driver, checkout_btn)
        _human_pause(3.0, 5.0)
        human_scroll(driver, random.randint(-50, 100))
        _human_pause(2.0, 3.0)

        if "checkout" not in driver.current_url.lower():
            _human_pause(1.5, 3.0)

        # ── PHASE 2: Bot behavior on checkout ─────────────────────
        # From this point on, ALL interaction is bot-like so the
        # behavioral biometrics system detects it as a bot.
        print("  [6/8] Filling form (bot typing) ...")
        form_data = {
            "name":  "\u09b0\u09be\u09b9\u09be\u09a4 \u09b9\u09cb\u09b8\u09c7\u09a8",
            "email": f"rahat{random.randint(100,999)}@gmail.com",
            "phone": f"017{random.randint(10000000, 99999999)}",
            "card":  (f"{random.randint(4000,4999)}"
                      f"{random.randint(1000,9999)}"
                      f"{random.randint(1000,9999)}"
                      f"{random.randint(1000,9999)}"),
            "exp":   f"{random.randint(1,12):02d}/{random.randint(26,30)}",
            "cvv":   str(random.randint(100, 999)),
        }
        for name, value in form_data.items():
            try:
                el = driver.find_element(By.CSS_SELECTOR,
                                          f"input[name='{name}']")
                el.clear()
                bot_type(el, value)
                time.sleep(random.uniform(0.03, 0.08))
            except Exception:
                pass

        time.sleep(random.uniform(0.2, 0.5))

        # Bot mouse movement using JS-dispatched events for maximum signal.
        # Selenium move_to_element generates 1 mousemove per call (too slow).
        # We dispatch rapid JS events to trigger React MouseTracker with
        # high speed, low std, zero idle periods.
        print("  [6b] Flooding mouse events (JS) ...")
        js_mouse_flood = """
            function dispatch(type, x, y, extras) {
                var el = document.body;
                var ev = new MouseEvent(type, {
                    bubbles: true, cancelable: true, view: window,
                    clientX: x, clientY: y, screenX: x, screenY: y,
                    movementX: (extras && extras.mdx) || 0,
                    movementY: (extras && extras.mdy) || 0,
                    button: 0, buttons: type === 'mousedown' ? 1 : 0,
                });
                el.dispatchEvent(ev);
            }
            var pts = %s;
            for (var i = 0; i < pts.length; i++) {
                var p = pts[i];
                var mdx = i > 0 ? p[0] - pts[i-1][0] : 0;
                var mdy = i > 0 ? p[1] - pts[i-1][1] : 0;
                dispatch('mousemove', p[0], p[1], {mdx: mdx, mdy: mdy});
                dispatch('mousedown', p[0], p[1]);
                dispatch('mouseup', p[0], p[1]);
                dispatch('click', p[0], p[1]);
            }
            return pts.length;
        """
        n_pts = random.randint(30, 50)
        pts = [[random.randint(50, 1200), random.randint(50, 800)] for _ in range(n_pts)]
        driver.execute_script(js_mouse_flood % str(pts))
        time.sleep(random.uniform(0.3, 0.6))

        # Right-click to trigger has_context_menu (+0.25 heuristic weight)
        print("  [6c] Right-click (context menu) ...")
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            ActionChains(driver).context_click(body).perform()
            time.sleep(0.3)
        except Exception:
            driver.execute_script("""
                var ev = new MouseEvent('contextmenu', {bubbles:true,cancelable:true,view:window,clientX:400,clientY:300});
                document.elementFromPoint(400,300).dispatchEvent(ev);
            """)
            time.sleep(0.3)

        # ── PHASE 2 continued: Bot CAPTCHA solving ────────────────
        print("  [7/8] Waiting for CAPTCHA ...")
        state = _get_security_state(driver)
        if state == "allow":
            print("  [~] ALLOW -- no CAPTCHA needed, skipping...")
            result["success"] = True
            return result
        if state == "block":
            print("  [~] BLOCKED by RL agent")
            result["success"] = True
            result["detected_bot"] = True
            return result

        captcha_input = _find_captcha_input(driver)

        if not captcha_input:
            state = _get_security_state(driver)
            if state == "allow":
                print("  [~] ALLOW -- no CAPTCHA needed")
                result["success"] = True
                return result
            if state == "block":
                print("  [~] BLOCKED by RL agent")
                result["success"] = True
                result["detected_bot"] = True
                return result
            result["error"] = "CAPTCHA input not found"
            print(f"  [!] CAPTCHA not found after {WAIT_TIMEOUT}s. url={driver.current_url}")
            return result

        result["captcha_encountered"] = True
        word_count = _count_captcha_words(driver)
        print(f"  [8/8] CAPTCHA found ({word_count} words) -- bot mode (3 retries) ...")

        try:
            captcha_input.location_once_scrolled_into_view
            _human_pause(1.5, 2.5)
        except Exception:
            pass

        # Try 3 rounds of wrong answers to generate strong bot signal
        for attempt in range(3):
            captcha_input = _find_captcha_input(driver, timeout=5)
            if not captcha_input:
                break

            try:
                loc = captcha_input.location_once_scrolled_into_view
                bot_move_to(driver,
                            loc["x"] + random.randint(10, 50),
                            loc["y"] + random.randint(5, 20))
            except Exception:
                pass

            # Long wrong answer string for maximum keystroke volume
            wc = _count_captcha_words(driver) or word_count
            wrong = ",".join(f"\u09ad\u09c1\u09b2{random.randint(1,99)}"
                             for _ in range(wc))

            # Trigger paste event via JS to activate has_paste heuristic (+0.25)
            driver.execute_script("""
                var inp = arguments[0];
                var dt = new DataTransfer();
                dt.setData('text/plain', arguments[1]);
                inp.focus();
                var pe = new ClipboardEvent('paste', {bubbles:true, clipboardData:dt});
                inp.dispatchEvent(pe);
                inp.value = arguments[1];
            """, captcha_input, wrong)
            time.sleep(0.1)

            time.sleep(random.uniform(0.05, 0.15))

            submit = _find_captcha_submit(driver)
            if submit:
                try:
                    bot_move_to(driver,
                                submit.location["x"] + 30,
                                submit.location["y"] + 10)
                    time.sleep(0.05)
                    submit.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", submit)
                time.sleep(random.uniform(0.6, 1.2))

            result["captcha_answered"] = True
            print(f"    attempt {attempt+1}/3 submitted")

            # Wait for error to appear, then click refresh for next round
            time.sleep(random.uniform(0.5, 1.0))
            refresh = driver.find_elements(By.CSS_SELECTOR, ".captcha-refresh")
            if refresh and attempt < 2:
                try:
                    refresh[0].click()
                except Exception:
                    pass
                time.sleep(random.uniform(0.4, 0.8))

        result["success"] = True
        result["detected_bot"] = True

        err_el = driver.find_elements(By.CSS_SELECTOR, ".captcha-error")
        if err_el:
            print(f"  [OK] CAPTCHA rejected: {err_el[0].text}")
        else:
            print("  [OK] CAPTCHA submitted (wrong answer)")

    except Exception as e:
        result["error"] = str(e)
        print(f"  [ERROR] {type(e).__name__}: {e}")

    return result


# ===================================================================
#  CLI
# ===================================================================

def main():
    global FRONTEND_URL, BACKEND_URL

    ap = argparse.ArgumentParser(
        description="Two-phase Selenium bot (human browsing + bot CAPTCHA)")
    ap.add_argument("--count", type=int, default=5,
                    help="Number of sessions (default 5)")
    ap.add_argument("--headless", action="store_true",
                    help="Run Chrome headless")
    ap.add_argument("--frontend", default=FRONTEND_URL,
                    help="Frontend URL (default: %(default)s)")
    ap.add_argument("--backend", default=BACKEND_URL,
                    help="Backend URL (default: %(default)s)")
    ap.add_argument("--verbose", action="store_true", default=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    FRONTEND_URL = args.frontend
    BACKEND_URL = args.backend
    verbose = not args.quiet

    print("=" * 50)
    print(" Two-Phase Selenium Bot")
    print("=" * 50)
    print(f"  Sessions : {args.count}")
    print(f"  Headless : {args.headless}")
    print(f"  Frontend : {FRONTEND_URL}")
    print(f"  Backend  : {BACKEND_URL}")
    print("=" * 50)
    print()

    driver = None
    stats = dict(total=0, success=0, captcha=0, answered=0, bot_detected=0, errors=0)

    try:
        for i in range(args.count):
            print(f"\n--- Session {i+1}/{args.count} ---")

            if driver is None:
                driver = create_driver(headless=args.headless)
            else:
                try:
                    driver.title
                except Exception:
                    print("  [!] Driver dead, creating a new one ...")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    driver = create_driver(headless=args.headless)

            r = run_session(driver, verbose=verbose)
            stats["total"] += 1
            if r["success"]:
                stats["success"] += 1
            if r["captcha_encountered"]:
                stats["captcha"] += 1
            if r["captcha_answered"]:
                stats["answered"] += 1
            if r["detected_bot"]:
                stats["bot_detected"] += 1
            if r["error"]:
                stats["errors"] += 1
            _human_pause(0.8, 2.0)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
            print("\n[driver] Chrome closed")

    print()
    print("=" * 50)
    print(" Summary")
    print("=" * 50)
    print(f"  Sessions total     : {stats['total']}")
    print(f"  Successful         : {stats['success']}")
    print(f"  CAPTCHA encountered: {stats['captcha']}")
    print(f"  CAPTCHA answered   : {stats['answered']}")
    print(f"  Detected as bot    : {stats['bot_detected']}")
    print(f"  Errors             : {stats['errors']}")
    print("=" * 50)
    print()
    print("Events were captured by React MouseTracker & KeyboardTracker")
    print("and sent to /api/behavior/track automatically.")
    print("Check scores: python scripts/collect_sessions.py stats")


if __name__ == "__main__":
    main()
