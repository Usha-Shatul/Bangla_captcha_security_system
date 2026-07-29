import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from database.models import get_db

db = get_db()

print("=== Access Count by Type (total events) ===")
rows = db.execute(
    "SELECT is_bot, COUNT(*) as total_events FROM behavior_logs GROUP BY is_bot"
).fetchall()
for r in rows:
    label = "Bot" if r["is_bot"] else "Human"
    print(f"  {label:>6s}: {r['total_events']}")

print("\n=== Unique Sessions by Type ===")
rows2 = db.execute(
    "SELECT is_bot, COUNT(DISTINCT session_id) as sessions FROM behavior_logs GROUP BY is_bot"
).fetchall()
for r in rows2:
    label = "Bot" if r["is_bot"] else "Human"
    print(f"  {label:>6s}: {r['sessions']}")

print("\n=== Unique IPs by Type ===")
rows3 = db.execute(
    "SELECT is_bot, COUNT(DISTINCT user_ip) as ips FROM behavior_logs WHERE user_ip IS NOT NULL GROUP BY is_bot"
).fetchall()
for r in rows3:
    label = "Bot" if r["is_bot"] else "Human"
    print(f"  {label:>6s}: {r['ips']}")

db.close()
