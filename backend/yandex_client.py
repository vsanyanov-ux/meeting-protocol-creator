import os
import time
import requests
from typing import Optional, List, Dict, Any
import json
import logging
import boto3
from typing import Optional, List

# Setting up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YandexClient:
    def __init__(self, api_key: str, folder_id: str, 
                 s3_access_key: Optional[str] = None, 
                 s3_secret_key: Optional[str] = None,
                 s3_bucket: Optional[str] = None,
                 gpt_model: str = "yandexgpt/latest"):
        self.api_key = api_key
        self.folder_id = folder_id
        self.s3_access_key = s3_access_key
        self.s3_secret_key = s3_secret_key
        self.s3_bucket = s3_bucket
        self.gpt_model = gpt_model
        self.stt_url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
        self.gpt_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        self.operation_url = "https://operation.api.cloud.yandex.net/operations/"

    def upload_to_s3(self, file_path: str, object_name: str) -> Optional[str]:
        """Upload file to Yandex Object Storage and return the URL."""
        if not all([self.s3_access_key, self.s3_secret_key, self.s3_bucket]):
            logger.error("S3 credentials or bucket missing.")
            return None
        
        # Yandex Object Storage is S3-compatible
        session = boto3.session.Session()
        s3 = session.client(
            service_name='s3',
            endpoint_url='https://storage.yandexcloud.net',
            aws_access_key_id=self.s3_access_key,
            aws_secret_access_key=self.s3_secret_key
        )
        
        try:
            s3.upload_file(file_path, self.s3_bucket, object_name)
            # Private URL with long expiry or public if configured. 
            # SpeechKit Async needs a URL it can access.
            # Easiest way is a presigned URL.
            url = s3.generate_presigned_url('get_object',
                                            Params={'Bucket': self.s3_bucket, 'Key': object_name},
                                            ExpiresIn=3600)
            return url
        except Exception as e:
            logger.error(f"S3 Upload Error: {e}")
            return None

    def transcribe_short(self, file_content: bytes, lang: str = "ru-RU") -> Optional[str]:
        """Recognize short audio (up to 30s). Returns the recognized text."""
        headers = {
            "Authorization": f"Api-Key {self.api_key}"
        }
        params = {
            "folderId": self.folder_id,
            "lang": lang
        }
        response = requests.post(self.stt_url, headers=headers, params=params, data=file_content)
        if response.status_code == 200:
            return response.json().get("result")
        else:
            logger.error(f"STT Error: {response.status_code} - {response.text}")
            return None

    def transcribe_long(self, file_url: str, lang: str = "ru-RU") -> Optional[str]:
        """Recognize long audio from a URL (Yandex Object Storage)."""
        headers = {
            "Authorization": f"Api-Key {self.api_key}"
        }
        body = {
            "config": {
                "specification": {
                    "languageCode": lang,
                    "model": "general",
                    "profanityFilter": False,
                    "partialResults": False
                }
            },
            "audio": {
                "uri": file_url
            }
        }
        
        # Start async operation
        response = requests.post("https://transcription.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize", 
                                headers=headers, json=body)
        
        if response.status_code != 200:
            logger.error(f"Long STT Start Error: {response.status_code} - {response.text}")
            return None
        
        operation_id = response.json().get("id")
        logger.info(f"Started long STT operation: {operation_id}")

        # Poll for completion
        while True:
            time.sleep(10)
            status_response = requests.get(f"{self.operation_url}{operation_id}", headers=headers)
            if status_response.status_code != 200:
                logger.error(f"Operation status check error: {status_response.text}")
                return None
            
            status_data = status_response.json()
            if status_data.get("done"):
                # Extract text from chunks
                chunks = status_data.get("response", {}).get("chunks", [])
                text = " ".join([chunk.get("alternatives", [{}])[0].get("text", "") for chunk in chunks])
                return text
            
            logger.info("Transcription in progress...")

    def create_protocol(self, transcription: str) -> Dict[str, Any]:
        """
        Use Yandex GPT to summarize transcription into a formal protocol.

        Returns dict:
            {
                "text": str | None,       # сгенерированный протокол
                "latency_ms": int,        # время ответа API в мс
                "input_tokens": int | None,
                "output_tokens": int | None,
                "messages": list           # prompt для Langfuse
            }
        """
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        system_text = (
            "Ты — ведущий эксперт по корпоративному управлению. "
            "Твоя задача — трансформировать расшифровку аудио в безупречный протокол совещания по международным стандартам. "
            "Используй Markdown заголовки '##'.\n\n"
            "СТРУКТУРА:\n"
            "## Общая информация\n"
            "Дата: [укажи если есть, иначе ____]\n"
            "Тема: [четкая формулировка]\n\n"
            "## Участники\n"
            "Присутствовали: [имена и роли]\n\n"
            "## Повестка дня\n"
            "[краткий список вопросов]\n\n"
            "## Ход обсуждения\n"
            "[аналитическое резюме дискуссии, основные аргументы]\n\n"
            "## Принятые решения и Поручения\n"
            "| № | Поручение | Ответственный | Срок исполнения |\n"
            "|---|-----------|---------------|-----------------|\n"
            "| 1 | Описание задачи | ФИО | Срок |\n\n"
            "## Нерешенные вопросы\n"
            "[вопросы, оставшиеся без ответа]"
        )
        messages = [
            {"role": "system", "text": system_text},
            {"role": "user", "text": f"Составь подробный протокол совещания на основе следующего текста:\n\n{transcription}"}
        ]
        prompt = {
            "modelUri": f"gpt://{self.folder_id}/{self.gpt_model}",
            "completionOptions": {"stream": False, "temperature": 0.3, "maxTokens": "2000"},
            "messages": messages
        }

        result = {"text": None, "latency_ms": 0, "input_tokens": None, "output_tokens": None, "messages": messages}

        t_start = time.time()
        response = requests.post(self.gpt_url, headers=headers, json=prompt)
        result["latency_ms"] = int((time.time() - t_start) * 1000)

        if response.status_code == 200:
            data = response.json()
            try:
                result["text"] = data["result"]["alternatives"][0]["message"]["text"]
                # Yandex GPT возвращает usage если доступно
                usage = data["result"].get("usage", {})
                result["input_tokens"] = usage.get("inputTextTokens")
                result["output_tokens"] = usage.get("completionTokens")
            except (KeyError, IndexError):
                logger.error(f"Malformed GPT response: {data}")
        else:
            logger.error(f"GPT Error: {response.status_code} - {response.text}")

        return result
