import os
import time
import requests
import json
import boto3
import shutil
import subprocess
import asyncio
from typing import Optional, List, Dict, Any, Callable
from loguru import logger

from .base import BaseAIProvider
from exceptions import ProviderQuotaError, ProviderNetworkError

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

    @property
    def model_name(self) -> str:
        # returns e.g. 'yandexgpt/latest'
        return self.gpt_model

    async def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds using ffprobe."""
        try:
            cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", audio_path
            ]
            result = await asyncio.to_thread(
                subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True
            )
            return float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Could not get audio duration: {e}")
            return 0.0

    async def transcribe_audio(
        self, 
        audio_path: str, 
        file_id: str, 
        status_updater: Callable[[str, str], None],
        trace: Any
    ) -> Optional[str]:
        # Get duration for STT pricing (Langfuse)
        duration_sec = await self._get_audio_duration(audio_path)
        if trace and hasattr(trace, "log_stt"):
            trace.log_stt(duration_sec)

        # S3 upload disabled, falling back to chunking
        status_updater("transcribing", f"Processing {int(duration_sec)}s audio via Yandex SpeechKit...")
        chunk_prefix = os.path.join(os.path.dirname(audio_path), f"chunks_{file_id}")
        if not os.path.exists(chunk_prefix):
            os.makedirs(chunk_prefix)
            
        try:
            await asyncio.to_thread(
                subprocess.run,
                [
                    "ffmpeg", "-y", "-i", audio_path, 
                    "-f", "segment", "-segment_time", "25",
                    "-c", "copy",
                    os.path.join(chunk_prefix, "chunk_%03d.ogg")
                ], 
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            
            chunk_files = sorted([f for f in os.listdir(chunk_prefix) if f.endswith(".ogg")])
            transcription_parts = []
            
            for i, chunk_file in enumerate(chunk_files):
                status_updater("transcribing", f"Transcribing segment {i+1} of {len(chunk_files)}...")
                chunk_path = os.path.join(chunk_prefix, chunk_file)
                with open(chunk_path, "rb") as f:
                    chunk_bytes = f.read()
                
                part = await self._transcribe_short(chunk_bytes)
                if part:
                    transcription_parts.append(part)
            
            return " ".join(transcription_parts)
        except Exception as e:
            logger.error(f"Chunking/Transcription error: {e}")
            if trace: trace.end_span("transcription_chunked", {"error": str(e)}, level="ERROR")
            return None
        finally:
            if os.path.exists(chunk_prefix):
                await asyncio.to_thread(shutil.rmtree, chunk_prefix)

    async def _upload_to_s3(self, file_path: str, object_name: str) -> Optional[str]:
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
            await asyncio.to_thread(s3.upload_file, file_path, self.s3_bucket, object_name)
            # Use native S3 URI format for SpeechKit instead of presigned URLs
            return f"s3://{self.s3_bucket}/{object_name}"
        except Exception as e:
            logger.error(f"S3 Upload Error: {e}")
            return None

    async def _transcribe_short(self, file_content: bytes, lang: str = "ru-RU") -> Optional[str]:
        headers = {"Authorization": f"Api-Key {self.api_key}"}
        params = {"folderId": self.folder_id, "lang": lang}
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    requests.post, self.stt_url, headers=headers, params=params, data=file_content, timeout=30
                )
                if response.status_code == 200:
                    return response.json().get("result")
                elif response.status_code in [429, 500, 502, 503, 504]:
                    logger.warning(f"STT retryable error {response.status_code} (attempt {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                elif response.status_code in [402, 403]:
                    logger.error(f"STT Quota/Auth Error: {response.status_code} - {response.text}")
                    raise ProviderQuotaError(f"Yandex STT Quota Exceeded: {response.text}", provider_name="yandex")
                
                logger.error(f"STT Fatal Error: {response.status_code} - {response.text}")
                return None
            except requests.exceptions.RequestException as e:
                logger.warning(f"STT Network issue (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise ProviderNetworkError(f"Yandex STT Network failed after {max_retries} attempts: {e}")
        return None

    async def _transcribe_long(self, file_url: str, lang: str = "ru-RU") -> Optional[str]:
        headers = {"Authorization": f"Api-Key {self.api_key}"}
        # file_url is now expected to be in s3://bucket/key format
        body = {
            "config": {
                "specification": {
                    "languageCode": lang, 
                    "model": "general", 
                    "profanityFilter": False, 
                    "partialResults": False,
                    "audioEncoding": "OGG_OPUS",
                    "diarizationConfig": {"enable": True}
                }
            },
            "audio": {"uri": file_url}
        }
        try:
            # transcribe.api is the correct, resolvable endpoint for long STT v2
            response = await asyncio.to_thread(
                requests.post, "https://transcribe.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize", 
                headers=headers, json=body, timeout=30
            )
            if response.status_code != 200:
                logger.error(f"Long STT Start Error: {response.status_code} - {response.text}")
                return None
            operation_id = response.json().get("id")
        except requests.exceptions.RequestException as e:
            logger.error(f"Long STT Network Error: {e}")
            return None
            
        max_retries = 360 # ~1 hour timeout total
        attempts = 0
        while attempts < max_retries:
            await asyncio.sleep(10)
            attempts += 1
            try:
                status_response = await asyncio.to_thread(
                    requests.get, f"{self.operation_url}{operation_id}", headers=headers, timeout=10
                )
                if status_response.status_code != 200:
                    logger.error(f"Operation status check error: {status_response.text}")
                    return None
                status_data = status_response.json()
                if status_data.get("done"):
                    chunks = status_data.get("response", {}).get("chunks", [])
                    
                    full_text = []
                    for chunk in chunks:
                        text = chunk.get("alternatives", [{}])[0].get("text", "").strip()
                        if text:
                            full_text.append(text)
                            
                    return " ".join(full_text).strip()
            except requests.exceptions.RequestException as e:
                logger.warning(f"Status check connection issue (attempt {attempts}): {e}")
                
        logger.error("Long STT timed out after 1 hour.")
        return None

    async def create_protocol(self, transcription: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Api-Key {self.api_key}", "Content-Type": "application/json"}
        system_text = (
            "Ты — ведущий эксперт по техническому документообороту и промышленному инжинирингу. Твоя задача — составить официальный протокол совещания на основе расшифровки.\n\n"
            "ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:\n"
            "1. ЯЗЫК: ВЕСЬ ответ должен быть СТРОГО на РУССКОМ языке. Использование английского языка ЗАПРЕЩЕНО (кроме технических кодов и брендов).\n"
            "2. СОХРАННОСТЬ ДАННЫХ: Обязательно сохраняй технические маркировки, артикулы, названия сплавов, коды изделий (например: марки стали 08Х18Н10Т, ГОСТы, чертежи).\n"
            "3. ТОЧНОСТЬ: Будь точен в числовых параметрах и единицах измерения.\n"
            "4. ТАБЛИЦА ПОРУЧЕНИЙ: Секцию 'Принятые решения и Поручения' ОБЯЗАТЕЛЬНО оформляй в виде Markdown-таблицы. ЗАПРЕЩЕНО использовать списки для задач.\n\n"
            "СТРУКТУРА ОТВЕТА:\n"
            "## Общая информация\n"
            "## Участники\n"
            "## Повестка дня\n"
            "## Ход обсуждения\n"
            "## Принятые решения и Поручения\n"
            "| № | Поручение | Ответственный | Срок исполнения |\n"
            "|---|-----------|---------------|------------------|\n"
            "| 1 | Описание задачи | Фамилия И.О. | ДД.ММ.ГГГГ или статус |\n\n"
            "## Нерешенные вопросы\n\n"
            "ПИШИ ТОЛЬКО НА РУССКОМ. БУДЬ ЛАКОНИЧНЫМ И СТРОГИМ."
        )
        messages = [
            {"role": "system", "text": system_text},
            {"role": "user", "text": f"Внимательно изучи расшифровку и составь подробный протокол НА РУССКОМ ЯЗЫКЕ:\n\n{transcription}"}
        ]
        prompt = {
            "modelUri": f"gpt://{self.folder_id}/{self.gpt_model}",
            "completionOptions": {"stream": False, "temperature": 0.2, "maxTokens": "2000"},
            "messages": messages
        }
        result = {"text": None, "latency_ms": 0, "input_tokens": None, "output_tokens": None, "messages": messages}
        t_start = time.time()
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(requests.post, self.gpt_url, headers=headers, json=prompt, timeout=120)
                result["latency_ms"] = int((time.time() - t_start) * 1000)

                if response.status_code == 200:
                    data = response.json()
                    result["text"] = data["result"]["alternatives"][0]["message"]["text"]
                    usage = data["result"].get("usage", {})
                    result["input_tokens"] = usage.get("inputTextTokens")
                    result["output_tokens"] = usage.get("completionTokens")
                    return result
                elif response.status_code in [429, 500, 502, 503, 504]:
                    logger.warning(f"GPT retryable error {response.status_code} (attempt {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                elif response.status_code in [402, 403]:
                    logger.error(f"GPT Quota/Auth Error: {response.status_code} - {response.text}")
                    raise ProviderQuotaError(f"Yandex GPT Quota Exceeded: {response.text}", provider_name="yandex")
                
                logger.error(f"GPT Fatal Error: {response.status_code} - {response.text}")
                break
            except Exception as e:
                logger.warning(f"GPT Attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                logger.error(f"GPT Error: {e}")
                break
            
        return result

    async def verify_protocol(self, transcription: str, protocol: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Api-Key {self.api_key}", "Content-Type": "application/json"}
        system_text = (
            "Ты — строгий корпоративный аудитор. Твоя задача: Сравнить РАСШИФРОВКУ и готовый ПРОТОКОЛ.\n"
            "ОБЯЗАТЕЛЬНО пиши отчет ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.\n"
            "Найди любые расхождения, пропущенные поручения или фактические ошибки.\n"
            "Оцени качество протокола по 5-балльной шкале по трем критериям:\n"
            "1. completeness (полнота) — все ли важные темы и поручения из расшифровки попали в протокол.\n"
            "2. accuracy (точность) — нет ли в протоколе искажений смысла или выдуманных фактов.\n"
            "3. hallucinations (отсутствие галлюцинаций) — 5 баллов если лишней информации нет, 1 балл если AI много выдумал.\n\n"
            "Выдай краткий отчет на русском языке.\n\n"
            "В конце ответа ОБЯЗАТЕЛЬНО добавь блок JSON для автоматической обработки:\n"
            "```json\n"
            "{\n"
            "  \"scores\": {\n"
            "    \"completeness\": 5,\n"
            "    \"accuracy\": 5,\n"
            "    \"hallucinations\": 5\n"
            "  }\n"
            "}\n"
            "```"
        )
        messages = [
            {"role": "system", "text": system_text},
            {"role": "user", "text": f"РАСШИФРОВКА:\n{transcription}\n\nПРОТОКОЛ:\n{protocol}"}
        ]
        prompt = {
            "modelUri": f"gpt://{self.folder_id}/{self.gpt_model}",
            "completionOptions": {"stream": False, "temperature": 0.1, "maxTokens": "1000"},
            "messages": messages
        }
        
        result = {
            "verification_report": "Проверка не выполнена", 
            "input_tokens": 0, 
            "output_tokens": 0,
            "latency_ms": 0,
            "scores": {}
        }
        t_start = time.time()
        try:
            response = await asyncio.to_thread(requests.post, self.gpt_url, headers=headers, json=prompt, timeout=120)
            result["latency_ms"] = int((time.time() - t_start) * 1000)
            if response.status_code == 200:
                data = response.json()
                text = data["result"]["alternatives"][0]["message"]["text"]
                result["verification_report"] = text
                
                # Попытка извлечь JSON с оценками
                try:
                    import re
                    json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
                    if json_match:
                        score_data = json.loads(json_match.group(1))
                        result["scores"] = score_data.get("scores", {})
                        logger.info(f"✅ Auditor scores extracted: {result['scores']}")
                except Exception as je:
                    logger.warning(f"Could not parse auditor scores: {je}")

                usage = data["result"].get("usage", {})
                result["input_tokens"] = usage.get("inputTextTokens")
                result["output_tokens"] = usage.get("completionTokens")
        except Exception as e:
            logger.error(f"Verification Error: {e}")
            
        return result

    async def format_transcript_with_ai(self, transcription: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Api-Key {self.api_key}", "Content-Type": "application/json"}
        system_text = (
            "Ты — эксперт по лингвистическому анализу диалогов. Твоя задача: превратить сплошной текст расшифровки в структурированный диалог.\n\n"
            "ПРАВИЛА:\n"
            "1. Распознавай смену спикеров по смыслу, вопросам и реакции. \n"
            "2. ОСОБОЕ ВНИМАНИЕ: Короткие наводящие вопросы ('Что дальше?', 'Как это?', 'Какой капкан?') почти всегда принадлежат ДРУГОМУ участнику (Участнику 1), который ведет беседу.\n"
            "3. Используй метки: 'Участник 1:', 'Участник 2:'. \n"
            "4. НЕ МЕНЯЙ СЛОВА. Только расставляй переносы строк, знаки препинания и метки спикеров.\n\n"
            "ПРИМЕР:\n"
            "Вход: привет как дела хорошо а у тебя тоже отлично что нового\n"
            "Выход:\n"
            "Участник 1: Привет. Как дела?\n"
            "Участник 2: Хорошо. А у тебя?\n"
            "Участник 1: Тоже отлично. Что нового?"
        )
        messages = [
            {"role": "system", "text": system_text},
            {"role": "user", "text": f"РАСШИФРОВКА (сплошной текст):\n{transcription}"}
        ]
        prompt = {
            "modelUri": f"gpt://{self.folder_id}/{self.gpt_model}",
            "completionOptions": {"stream": False, "temperature": 0.1, "maxTokens": "4000"},
            "messages": messages
        }
        
        result = {"formatted_text": transcription, "input_tokens": 0, "output_tokens": 0}
        try:
            response = await asyncio.to_thread(requests.post, self.gpt_url, headers=headers, json=prompt, timeout=120)
            if response.status_code == 200:
                data = response.json()
                result["formatted_text"] = data["result"]["alternatives"][0]["message"]["text"]
                usage = data["result"].get("usage", {})
                result["input_tokens"] = usage.get("inputTextTokens")
                result["output_tokens"] = usage.get("completionTokens")
            else:
                logger.error(f"Transcript formatting error: {response.text}")
        except Exception as e:
            logger.error(f"Transcript formatting crash: {e}")
            
        return result
