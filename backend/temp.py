import sys, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
conn=sqlite3.connect('storage/status.db')
for row in conn.execute('SELECT file_id, data FROM tasks'):
    print(row[0], row[1])
