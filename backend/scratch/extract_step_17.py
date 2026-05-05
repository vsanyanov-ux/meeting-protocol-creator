import json
import os

log_path = r'C:\Users\vanya\.gemini\antigravity\brain\c3af7e49-d1bb-4822-b252-2638b0f8f35b\.system_generated\logs\overview.txt'

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get('step_index') == 17: # Step 6 in the list was step_index 17
                content = data.get('content', '')
                with open('backend/scratch/step_17_full.txt', 'w', encoding='utf-8') as out:
                    out.write(content)
                print("Done")
                break
        except:
            continue
