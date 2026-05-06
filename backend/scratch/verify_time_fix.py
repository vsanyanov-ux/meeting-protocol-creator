import sqlite3
import os

STORAGE_DIR = "storage"
db_path = os.path.join(STORAGE_DIR, "status.db")

if os.path.exists(db_path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT file_id, strftime('%Y-%m-%dT%H:%M:%SZ', updated_at) FROM tasks LIMIT 5")
        rows = cursor.fetchall()
        print("Verification of timestamp format:")
        for row in rows:
            print(f"File ID: {row[0]}, Formatted Time: {row[1]}")
else:
    print(f"Database not found at {db_path}")
