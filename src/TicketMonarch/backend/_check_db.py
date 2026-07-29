import sys
import io
import json
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from database.models import get_db

db = get_db()
rows = db.execute(
    "SELECT id, session_id, difficulty, word_list FROM captcha_sessions"
).fetchall()
for row in rows:
    wl = json.loads(row["word_list"])
    ctype = wl.get("captcha_type", "?")
    print(
        f'#{row["id"]} session={row["session_id"]} '
        f'diff={row["difficulty"]} type={ctype}'
    )
db.close()
