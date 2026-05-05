import asyncio
import aiohttp
import time
import os
import uuid
import sys

# Ensure UTF-8 output if possible, but we'll also use safe printing
API_BASE_URL = "http://localhost:8000"

async def upload_and_poll(session, file_path, index):
    print(f"[{index}] Starting upload: {file_path}")
    
    # Upload
    data = aiohttp.FormData()
    f = open(file_path, 'rb')
    try:
        data.add_field('file', f, filename=f"stress_{index}_{os.path.basename(file_path)}")
        data.add_field('provider', 'local')
        data.add_field('recipient_email', 'stress_test@example.com')
        data.add_field('session_id', f"stress-session-{uuid.uuid4().hex[:8]}")

        async with session.post(f"{API_BASE_URL}/process-meeting", data=data) as resp:
            if resp.status != 200:
                print(f"[{index}] Upload failed: {await resp.text()}")
                return False
            
            file_id = (await resp.json())["file_id"]
            print(f"[{index}] Uploaded! File ID: {file_id}")
    finally:
        f.close()

    # Poll status
    while True:
        async with session.get(f"{API_BASE_URL}/status/{file_id}") as resp:
            if resp.status != 200:
                print(f"[{index}] Status fetch failed")
                return False
            
            data = await resp.json()
            status = data.get("status")
            message = data.get("message", "")
            
            # Safe print to avoid UnicodeEncodeError
            try:
                print(f"[{index}] Status: {status} | {message}")
            except UnicodeEncodeError:
                print(f"[{index}] Status: {status} | [Message contains non-ASCII characters]")
            
            if status == "completed":
                print(f"[{index}] SUCCESS!")
                return True
            elif status == "error":
                print(f"[{index}] FAILED: {message}")
                return False
        
        await asyncio.sleep(5)

async def main():
    # Create 5 small test files
    test_files = []
    for i in range(5):
        fname = f"test_load_{i}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"This is a stress test file number {i}. It contains some text to be analyzed by the system.")
        test_files.append(fname)

    print("=== STARTING STRESS TEST: 5 SIMULTANEOUS PROTOCOLS ===")
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = [upload_and_poll(session, test_files[i], i) for i in range(5)]
        results = await asyncio.gather(*tasks)

    duration = time.time() - start_time
    success_count = sum(1 for r in results if r)
    
    print("\n=== STRESS TEST SUMMARY ===")
    print(f"Total tasks: 5")
    print(f"Successes: {success_count}")
    print(f"Failures: {5 - success_count}")
    print(f"Total duration: {duration:.2f} seconds")
    
    # Cleanup
    for f in test_files:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

if __name__ == "__main__":
    asyncio.run(main())
