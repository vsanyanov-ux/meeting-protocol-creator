import sqlite3
import json
import os

db_path = 'backend/storage/status.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.execute('SELECT file_id, data, updated_at FROM tasks ORDER BY updated_at DESC LIMIT 5')
rows = cursor.fetchall()

print("=== LAST 5 TASKS IN DATABASE ===")
for row in rows:
    file_id = row[0]
    data = json.loads(row[1])
    updated_at = row[2]
    status = data.get('status', 'N/A')
    message = data.get('message', 'N/A')
    print(f"ID: {file_id}")
    print(f"  Status:  {status}")
    print(f"  Message: {message}")
    print(f"  Updated: {updated_at}")
    print("-" * 30)

conn.close()
