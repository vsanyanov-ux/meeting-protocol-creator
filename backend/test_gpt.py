import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("YANDEX_API_KEY")
folder_id = os.getenv("YANDEX_FOLDER_ID")
gpt_model = os.getenv("YANDEX_GPT_MODEL", "yandexgpt/latest")

headers = {
    "Authorization": f"Api-Key {api_key}",
    "Content-Type": "application/json"
}
        
prompt = {
    "modelUri": f"gpt://{folder_id}/{gpt_model}",
    "completionOptions": {
        "stream": False,
        "temperature": 0.3,
        "maxTokens": "2000"
    },
    "messages": [
        {
            "role": "user",
            "text": "test"
        }
    ]
}

response = requests.post("https://llm.api.cloud.yandex.net/foundationModels/v1/completion", headers=headers, json=prompt)
print(f"Json: {response.json()}")
