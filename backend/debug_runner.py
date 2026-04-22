import traceback
import sys
import os

print("--- DEBUG RUNNER STARTING ---")
try:
    from main import app
    import uvicorn
    print("Dependencies loaded, starting uvicorn...")
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level="debug")
except Exception as e:
    print("!!! CRITICAL CRASH DETECTED !!!")
    with open("crash_report.txt", "w", encoding='utf-8') as f:
        f.write(f"Timestamp: {os.times()}\n")
        f.write(traceback.format_exc())
    traceback.print_exc()
    sys.exit(1)
finally:
    print("--- DEBUG RUNNER EXITED ---")
