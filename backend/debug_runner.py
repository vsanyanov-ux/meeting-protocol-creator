import subprocess
import os
import sys
import time

def kill_port_8000():
    try:
        # Windows command to find and kill process on port 8000
        output = subprocess.check_output('netstat -ano | findstr :8000', shell=True).decode()
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) > 4:
                pid = parts[-1]
                print(f"Killing process {pid} on port 8000...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True)
    except Exception:
        pass

def run_server():
    print("--- DEBUG RUNNER STARTING ---")
    kill_port_8000()
    
    # Run main.py directly
    cmd = [sys.executable, "main.py"]
    
    try:
        process = subprocess.Popen(cmd)
        print(f"Server started with PID {process.pid}")
        process.wait()
    except KeyboardInterrupt:
        print("\nStopping server...")
        process.terminate()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("--- DEBUG RUNNER EXITED ---")

if __name__ == "__main__":
    run_server()
