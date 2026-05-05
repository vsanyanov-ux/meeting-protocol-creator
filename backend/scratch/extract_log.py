import json
import os

log_path = r'C:\Users\vanya\.gemini\antigravity\brain\c3af7e49-d1bb-4822-b252-2638b0f8f35b\.system_generated\logs\overview.txt'

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        if data.get('step_index') == 20:
            content = data.get('content', '')
            with open('backend/scratch/log_step_20.txt', 'w', encoding='utf-8') as out:
                out.write(content)
            print("Done writing to backend/scratch/log_step_20.txt")
            break
