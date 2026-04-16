import requests
import os
from dotenv import load_dotenv

load_dotenv()

ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
model = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

print(f"Testing connection to {ollama_url}")
print(f"Using model: {model}")

try:
    response = requests.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": False
        },
        timeout=60
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json().get('message', {}).get('content', '')}")
except Exception as e:
    print(f"Error: {e}")
