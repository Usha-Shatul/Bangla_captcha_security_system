import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from database.models import get_db

db = get_db()

print("=== Behavior Logs ===")
rows = db.execute(
    "SELECT label, is_bot, COUNT(*) as cnt FROM behavior_logs GROUP BY label, is_bot ORDER BY label"
).fetchall()
print(f"{'Label':>12s}  {'is_bot':>6s}  {'Count':>6s}")
print("-" * 32)
for r in rows:
    print(f'{r["label"]:>12s}  {str(r["is_bot"]):>6s}  {r["cnt"]:>6d}')

total = db.execute("SELECT COUNT(*) as c FROM behavior_logs").fetchone()
print(f"\nTotal behavior logs: {total['c']}")

print("\n=== Captcha Sessions ===")
rows2 = db.execute(
    "SELECT difficulty, solved, used, COUNT(*) as cnt FROM captcha_sessions GROUP BY difficulty, solved, used ORDER BY difficulty"
).fetchall()
print(f"{'Diff':>4s}  {'Solved':>6s}  {'Used':>4s}  {'Count':>6s}")
print("-" * 28)
for r in rows2:
    print(f'{r["difficulty"]:>4d}  {str(r["solved"]):>6s}  {str(r["used"]):>4s}  {r["cnt"]:>6d}')

total2 = db.execute("SELECT COUNT(*) as c FROM captcha_sessions").fetchone()
print(f"\nTotal sessions: {total2['c']}")

db.close()
