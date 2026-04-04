import os
import time
import requests
import json
import boto3
import shutil
import subprocess
from typing import Optional, List, Dict, Any, Callable
from loguru import logger

from .base import BaseAIProvider

class YandexProvider(BaseAIProvider):
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

    @property
    def name(self) -> str:
        return "yandex"

    def transcribe_audio(
        self, 
        audio_path: str, 
        file_id: str, 
        status_updater: Callable[[str, str], None],
        trace: Any
    ) -> Optional[str]:
        # Log: has_s3
        has_s3 = all([self.s3_access_key, self.s3_secret_key, self.s3_bucket])
        if has_s3:
            status_updater("uploading", "Uploading to Yandex Object Storage...")
            if trace: trace.start_span("s3_upload", {"bucket": self.s3_bucket})
            object_name = f"meetings/{file_id}_{os.path.basename(audio_path)}"
            file_url = self._upload_to_s3(audio_path, object_name)
            if trace: trace.end_span("s3_upload", {"url_generated": bool(file_url)})
            
            if file_url:
                status_updater("transcribing", "Transcribing audio (long operation)...")
                if trace: trace.start_span("transcription_long", {"method": "async_s3"})
                transcription = self._transcribe_long(file_url)
                if trace: trace.end_span("transcription_long", {"chars": len(transcription) if transcription else 0})
                return transcription
                
        # Fallback to chunking
        status_updater("transcribing", "Processing long audio via chunking (No S3)...")
        chunk_prefix = os.path.join(os.path.dirname(audio_path), f"chunks_{file_id}")
        if not os.path.exists(chunk_prefix):
            os.makedirs(chunk_prefix)
            
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", audio_path, 
                "-f", "segment", "-segment_time", "25",
                "-c", "copy",
                os.path.join(chunk_prefix, "chunk_%03d.ogg")
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            chunk_files = sorted([f for f in os.listdir(chunk_prefix) if f.endswith(".ogg")])
            transcription_parts = []
            
            for i, chunk_file in enumerate(chunk_files):
                status_updater("transcribing", f"Transcribing segment {i+1} of {len(chunk_files)}...")
                chunk_path = os.path.join(chunk_prefix, chunk_file)
                with open(chunk_path, "rb") as f:
                    chunk_bytes = f.read()
                
                part = self._transcribe_short(chunk_bytes)
                if part:
                    transcription_parts.append(part)
            
            return " ".join(transcription_parts)
        except Exception as e:
            logger.error(f"Chunking/Transcription error: {e}")
            if trace: trace.end_span("transcription_chunked", {"error": str(e)}, level="ERROR")
            return None
        finally:
            if os.path.exists(chunk_prefix):
                shutil.rmtree(chunk_prefix)

    def _upload_to_s3(self, file_path: str, object_name: str) -> Optional[str]:
        if not all([self.s3_access_key, self.s3_secret_key, self.s3_bucket]):
            return None
        session = boto3.session.Session()
        s3 = session.client(
            service_name='s3',
            endpoint_url='https://storage.yandexcloud.net',
            aws_access_key_id=self.s3_access_key,
            aws_secret_access_key=self.s3_secret_key
        )
        try:
            s3.upload_file(file_path, self.s3_bucket, object_name)
            url = s3.generate_presigned_url('get_object',
                                            Params={'Bucket': self.s3_bucket, 'Key': object_name},
                                            ExpiresIn=3600)
            return url
        except Exception as e:
            logger.error(f"S3 Upload Error: {e}")
            return None

    def _transcribe_short(self, file_content: bytes, lang: str = "ru-RU") -> Optional[str]:
        headers = {"Authorization": f"Api-Key {self.api_key}"}
        params = {"folderId": self.folder_id, "lang": lang}
        try:
            response = requests.post(self.stt_url, headers=headers, params=params, data=file_content, timeout=30)
            if response.status_code == 200:
                return response.json().get("result")
            else:
                logger.error(f"STT Error: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"STT Network Error: {e}")
            return None

    def _transcribe_long(self, file_url: str, lang: str = "ru-RU") -> Optional[str]:
        headers = {"Authorization": f"Api-Key {self.api_key}"}
        body = {
            "config": {
                "specification": {
                    "languageCode": lang, "model": "general", "profanityFilter": False, "partialResults": False
                }
            },
            "audio": {"uri": file_url}
        }
        try:
            response = requests.post("https://transcription.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize", 
                                    headers=headers, json=body, timeout=30)
            if response.status_code != 200:
                logger.error(f"Long STT Start Error: {response.status_code} - {response.text}")
                return None
            operation_id = response.json().get("id")
        except requests.exceptions.RequestException as e:
            logger.error(f"Long STT Network Error: {e}")
            return None
            
        max_retries = 360 # ~1 hour timeout total for long async STT (360 * 10 sec)
        attempts = 0
        while attempts < max_retries:
            time.sleep(10)
            attempts += 1
            try:
                status_response = requests.get(f"{self.operation_url}{operation_id}", headers=headers, timeout=10)
                if status_response.status_code != 200:
                    logger.error(f"Operation status check error: {status_response.text}")
                    return None
                status_data = status_response.json()
                if status_data.get("done"):
                    chunks = status_data.get("response", {}).get("chunks", [])
                    text = " ".join([chunk.get("alternatives", [{}])[0].get("text", "") for chunk in chunks])
                    return text
            except requests.exceptions.RequestException as e:
                logger.warning(f"Status check connection issue (attempt {attempts}): {e}")
                
        logger.error("Long STT timed out after 1 hour.")
        return None

    def create_protocol(self, transcription: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Api-Key {self.api_key}", "Content-Type": "application/json"}
        system_text = (
            "Ты — ведущий эксперт по корпоративному управлению... \n"
            "СТРУКТУРА:\n## Общая информация\n## Участники\n## Повестка дня\n## Ход обсуждения\n"
            "## Принятые решения и Поручения\n| № | Поручение | Ответственный | Срок исполнения |\n"
            "## Нерешенные вопросы"
        )
        messages = [
            {"role": "system", "text": system_text},
            {"role": "user", "text": f"Составь подробный протокол совещания:\n\n{transcription}"}
        ]
        prompt = {
            "modelUri": f"gpt://{self.folder_id}/{self.gpt_model}",
            "completionOptions": {"stream": False, "temperature": 0.3, "maxTokens": "2000"},
            "messages": messages
        }
        result = {"text": None, "latency_ms": 0, "input_tokens": None, "output_tokens": None, "messages": messages}
        t_start = time.time()
        
        try:
            response = requests.post(self.gpt_url, headers=headers, json=prompt, timeout=120)
            result["latency_ms"] = int((time.time() - t_start) * 1000)

            if response.status_code == 200:
                data = response.json()
                try:
                    result["text"] = data["result"]["alternatives"][0]["message"]["text"]
                    usage = data["result"].get("usage", {})
                    result["input_tokens"] = usage.get("inputTextTokens")
                    result["output_tokens"] = usage.get("completionTokens")
                except (KeyError, IndexError):
                    logger.error(f"Malformed GPT response: {data}")
            else:
                logger.error(f"GPT Error: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"GPT Network Error: {e}")
            result["latency_ms"] = int((time.time() - t_start) * 1000)
            
        return result
