import sys, io, json, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sid = 'med-new-001'
data = json.dumps({'difficulty': 2, 'session_id': sid}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/api/captcha/generate', data=data, headers={'Content-Type': 'application/json'})
r = urllib.request.urlopen(req, timeout=15)
resp = json.loads(r.read())
print('ok:', resp.get('ok'))
print('target:', resp.get('target_category'))
print('grid cells:', len(resp.get('grid', [])))

import sqlite3
conn = sqlite3.connect(r'D:\Bangla_captcha\Adaptive-Bangla-CAPTCHA\TicketMonarch\backend\database\app.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('SELECT word_list FROM captcha_sessions WHERE session_id = ?', (sid,))
row = c.fetchone()
if row:
    stored = json.loads(row['word_list'])
    grid = stored.get('grid', [])
    target_positions = [g['position'] for g in grid if g['category'] == resp['target_category']]
    print('target_positions:', target_positions)

    data2 = json.dumps({
        'session_id': sid,
        'selected_positions': target_positions,
        'mouse': [], 'keyboard': [],
        'difficulty': 2, 'solve_time_ms': 8000
    }).encode()
    req2 = urllib.request.Request('http://127.0.0.1:8000/api/captcha/verify', data=data2, headers={'Content-Type': 'application/json'})
    r2 = urllib.request.urlopen(req2, timeout=10)
    vresp = json.loads(r2.read())
    print('verify correct:', vresp['correct'])
else:
    print('NOT IN DB')
conn.close()
