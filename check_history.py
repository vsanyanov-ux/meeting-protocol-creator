import os
import time

conversations_dir = r"C:\Users\vanya\.gemini\antigravity\conversations"
files = [os.path.join(conversations_dir, f) for f in os.listdir(conversations_dir) if f.endswith('.pb')]

# Sort by modification time
files.sort(key=os.path.getmtime)

print(f"Total conversations: {len(files)}")
print("\nOldest 5:")
for f in files[:5]:
    print(f"{os.path.basename(f)} - {time.ctime(os.path.getmtime(f))}")

print("\nNewest 5:")
for f in files[-5:]:
    print(f"{os.path.basename(f)} - {time.ctime(os.path.getmtime(f))}")
