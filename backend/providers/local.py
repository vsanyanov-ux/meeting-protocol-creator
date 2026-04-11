import os
import time
import requests
import json
import shutil
import subprocess
import asyncio
from typing import Optional, List, Dict, Any, Callable
from loguru import logger
from faster_whisper import WhisperModel
import ollama

from .base import BaseAIProvider

class LocalProvider(BaseAIProvider):
    def __init__(self, 
                 whisper_model_size: str = "medium", 
                 ollama_url: str = "http://localhost:11434",
                 ollama_model: str = "qwen3:7b"):
        self.whisper_model_size = whisper_model_size
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self._whisper_model = None
        self._model_verified = False
        
        # Determine device for Whisper (cuda/cpu)
        self.device = "cuda" if self._has_gpu() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        
        logger.info(f"Initialized LocalProvider with Whisper ({whisper_model_size}, {self.device}) and Ollama ({ollama_model})")

    async def _has_gpu(self) -> bool:
        try:
            # Quick check for nvidia-smi
            res = await asyncio.to_thread(
                subprocess.run, ["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
            return True
        except:
            return False

    async def _get_whisper(self):
        if self._whisper_model is None:
            logger.info(f"Loading Whisper model '{self.whisper_model_size}' on 'auto'...")
            self._whisper_model = await asyncio.to_thread(
                WhisperModel,
                self.whisper_model_size, 
                device="auto", 
                compute_type="float32",
                download_root="models_cache/whisper"
            )
        return self._whisper_model

    @property
    def name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self.ollama_model

    async def transcribe_audio(
        self, 
        audio_path: str, 
        file_id: str, 
        status_updater: Callable[[str, str], None],
        trace: Any
    ) -> Optional[str]:
        status_updater("transcribing", f"Loading Whisper ({self.whisper_model_size})...")
        model = await self._get_whisper()
        
        status_updater("transcribing", "Transcribing audio locally...")
        t_start = time.time()
        
        try:
            # transcribe is a generator, so we need to iterate or call in thread
            def run_transcription():
                segments, info = model.transcribe(audio_path, beam_size=5, language="ru")
                return list(segments), info

            segments, info = await asyncio.to_thread(run_transcription)
            
            full_text = []
            for segment in segments:
                full_text.append(segment.text)
                # We could update progress here based on segment timestamps vs info.duration
                
            transcription = " ".join(full_text).strip()
            duration_sec = info.duration
            latency_sec = time.time() - t_start
            
            logger.info(f"Local transcription finished in {latency_sec:.1f}s for {duration_sec:.1f}s audio.")
            return transcription
        except Exception as e:
            logger.error(f"Local transcription error: {e}")
            return None

    async def _ensure_model_exists(self, client: ollama.Client):
        if self._model_verified:
            return
        
        try:
            logger.info(f"Checking if Ollama model '{self.ollama_model}' is available...")
            response = await asyncio.to_thread(client.list)
            # client.list() returns a ListResponse object with a 'models' attribute
            model_names = [m.model for m in response.models]
            
            if self.ollama_model not in model_names and (self.ollama_model + ":latest") not in model_names:
                logger.info(f"Model '{self.ollama_model}' not found. Pulling it now (this might take a few minutes)...")
                await asyncio.to_thread(client.pull, self.ollama_model)
                logger.info(f"Model '{self.ollama_model}' pulled successfully.")
            
            self._model_verified = True
        except Exception as e:
            logger.error(f"Failed to verify/pull Ollama model: {e}")

    async def _call_ollama(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> Dict[str, Any]:
        result = {"text": None, "latency_ms": 0, "input_tokens": 0, "output_tokens": 0, "messages": messages}
        t_start = time.time()
        
        try:
            client = ollama.Client(host=self.ollama_url)
            await self._ensure_model_exists(client)
            
            response = await asyncio.to_thread(
                client.chat,
                model=self.ollama_model,
                messages=messages,
                options={"temperature": temperature}
            )
            
            result["latency_ms"] = int((time.time() - t_start) * 1000)
            result["text"] = response['message']['content']
            result["input_tokens"] = response.get('prompt_eval_count', 0)
            result["output_tokens"] = response.get('eval_count', 0)
            
        except Exception as e:
            logger.error(f"Ollama Error: {e}")
            
        return result

    async def create_protocol(self, transcription: str) -> Dict[str, Any]:
        system_text = (
            "Ты — ведущий эксперт по корпоративному управлению. Твоя задача — составить официальный протокол совещания на основе предоставленной расшифровки.\n\n"
            "СТРУКТУРА:\n## Общая информация\n## Участники\n## Повестка дня\n## Ход обсуждения\n"
            "## Принятые решения и Поручения\n"
            "| № | Поручение | Ответственный | Срок исполнения |\n"
            "|---|-----------|---------------|------------------|\n"
            "| 1 | Название задачи | ФИО ответственного | Срок |\n\n"
            "## Нерешенные вопросы\n\n"
            "Будь лаконичным. Секцию 'Принятые решения и Поручения' ОБЯЗАТЕЛЬНО оформляй СТРОГО в виде Markdown-таблицы (как в примере выше)."
        )
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": f"Составь подробный протокол совещания:\n\n{transcription}"}
        ]
        return await self._call_ollama(messages)

    async def verify_protocol(self, transcription: str, protocol: str) -> Dict[str, Any]:
        system_text = (
            "Ты — строгий корпоративный аудитор. Твоя задача: Сравнить РАСШИФРОВКУ и готовый ПРОТОКОЛ. \n"
            "Найди любые расхождения, пропущенные поручения или фактические ошибки. \n"
            "Выдай краткий отчет: что проверено и найдены ли критические ошибки."
        )
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": f"РАСШИФРОВКА:\n{transcription}\n\nПРОТОКОЛ:\n{protocol}"}
        ]
        res = await self._call_ollama(messages, temperature=0.1)
        return {
            "verification_report": res["text"] or "Ошибка верификации",
            "input_tokens": res["input_tokens"],
            "output_tokens": res["output_tokens"]
        }

    async def format_transcript_with_ai(self, transcription: str) -> Dict[str, Any]:
        system_text = (
            "Ты — эксперт по лингвистическому анализу диалогов. Твоя задача: превратить сплошной текст расшифровки в структурированный диалог.\n\n"
            "ПРАВИЛА:\n1. Распознавай смену спикеров по смыслу.\n2. Используй метки: 'Спикер 1:', 'Спикер 2:'.\n3. НЕ МЕНЯЙ СЛОВА."
        )
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": f"РАСШИФРОВКА:\n{transcription}"}
        ]
        res = await self._call_ollama(messages, temperature=0.1)
        return {
            "formatted_text": res["text"] or transcription,
            "input_tokens": res["input_tokens"],
            "output_tokens": res["output_tokens"]
        }
