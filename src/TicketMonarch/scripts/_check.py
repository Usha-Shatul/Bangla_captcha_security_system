import requests, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
r = requests.get("http://localhost:8000/api/behavior/history")
data = r.json()
logs = data.get("logs", [])
print(f"Total logs: {len(logs)}")
for log in logs[:6]:
    print(f"  id={log['id']} score={log['bot_score']} is_bot={log['is_bot']} "
          f"mouse={log['mouse_events']} kb={log['keyboard_events']} method={log['method']}")
