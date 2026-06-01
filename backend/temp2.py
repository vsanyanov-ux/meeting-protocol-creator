import sys, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
conn=sqlite3.connect('storage/status.db')
for row in conn.execute('SELECT file_id, data FROM tasks ORDER BY updated_at DESC LIMIT 5'):
    print(row[0], row[1])
