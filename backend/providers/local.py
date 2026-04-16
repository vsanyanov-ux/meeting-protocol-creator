import os
import time
import requests
import httpx
import json
import shutil
import subprocess
import asyncio
from typing import Optional, List, Dict, Any, Callable
from loguru import logger
import gc
import torch
from faster_whisper import WhisperModel
import ollama

from .base import BaseAIProvider
from exceptions import HardwareError

class LocalProvider(BaseAIProvider):
    def __init__(self, 
                 whisper_model_size: str = "medium", 
                 ollama_url: str = "http://127.0.0.1:11434",
                 ollama_model: str = "qwen3.5:9b",
                 device: Optional[str] = None):
        self.whisper_model_size = whisper_model_size
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self._whisper_model = None
        self._model_verified = False
        
        # Determine device for Whisper (cuda/cpu)
        if device:
            self.device = device
        else:
            env_device = os.getenv("WHISPER_DEVICE")
            if env_device:
                self.device = env_device
            else:
                self.device = "cuda" if self._has_gpu() else "cpu"
            
        # use int8_float16 for stability and speed on RTX cards
        # BUT if we are on CPU, we MUST use int8 or float32
        self.compute_type = "int8_float16" if self.device == "cuda" else "int8"
        
        logger.info(f"Initialized LocalProvider with Whisper ({whisper_model_size}, {self.device}, {self.compute_type}) and Ollama ({ollama_model})")

    def _has_gpu(self) -> bool:
        try:
            # First try nvidia-smi
            subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except:
            # Fallback for containers without nvidia-smi but with libraries and allocated device
            # Check for standard CUDA environment variables or device files in Linux
            has_dev = os.path.exists("/dev/nvidia0")
            has_env = os.environ.get("CUDA_VISIBLE_DEVICES") is not None
            
            # Additional check: try to import ctranslate2 and check device count
            try:
                import ctranslate2
                has_ct2_cuda = ctranslate2.get_cuda_device_count() > 0
            except:
                has_ct2_cuda = False
                
            return has_dev or has_env or has_ct2_cuda

    async def _cleanup_memory(self):
        """Deeply clean up VRAM and RAM after model usage."""
        if self._whisper_model is not None:
            logger.info("--- MEMORY CLEANUP: Unloading Whisper model ---")
            # Explicitly delete the model reference
            del self._whisper_model
            self._whisper_model = None
            
        # Standard Python GC
        gc.collect()
        
        # Clear CUDA cache if using GPU
        if self.device == "cuda":
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
                    logger.info("--- MEMORY CLEANUP: CUDA cache cleared successfully ---")
                else:
                    logger.warning("--- MEMORY CLEANUP: CUDA not available in Torch, skipping cache clear ---")
            except Exception as e:
                logger.warning(f"Could not clear CUDA cache: {e}")
                
    async def _get_whisper(self):
        if self._whisper_model is None:
            logger.info(f"--- WHISPER LOADING START: {self.whisper_model_size} on {self.device} ({self.compute_type}) ---")
            logger.info(f"Model path: models_cache/whisper")
            
            t_start = time.time()
            try:
                self._whisper_model = await asyncio.to_thread(
                    WhisperModel,
                    self.whisper_model_size, 
                    device=self.device, 
                    compute_type=self.compute_type,
                    download_root="models_cache/whisper"
                )
                logger.info(f"--- WHISPER LOADING COMPLETE in {time.time() - t_start:.1f}s ---")
            except Exception as e:
                logger.error(f"CRITICAL ERROR LOADING WHISPER: {e}")
                raise
        return self._whisper_model

    @property
    def name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self.ollama_model

    async def _unload_ollama_models(self):
        """Force Ollama to unload all models from VRAM."""
        try:
            logger.info("--- MEMORY OPTIMIZATION: Requesting Ollama to unload models ---")
            # We use a direct request to the /api/generate endpoint with keep_alive: 0
            # to force the current model to be unloaded.
            client = ollama.Client(host=self.ollama_url)
            await asyncio.to_thread(
                client.generate,
                model=self.ollama_model,
                prompt="",
                keep_alive=0
            )
            logger.info("--- MEMORY OPTIMIZATION: Ollama models unloaded ---")
        except Exception as e:
            logger.warning(f"Failed to unload Ollama models: {e}")

    async def transcribe_audio(
        self, 
        audio_path: str, 
        file_id: str, 
        status_updater: Callable[[str, str], None],
        trace: Any
    ) -> Optional[str]:
        # WITH 12GB VRAM, WE DON'T NEED TO UNLOAD MODELS SEQUENTIALLY
        # if self.device == "cuda":
        #     await self._unload_ollama_models()
        #     await self._cleanup_memory()
            
        status_updater("transcribing", f"Loading Whisper ({self.whisper_model_size})...")
        
        # TRANSCRIPTION SPAN FOR LANGFUSE
        trace.start_span("transcription")
        try:
            model = await self._get_whisper()
            
            status_updater("transcribing", f"Processing via Local Whisper ({self.whisper_model_size})...")
            logger.info(f"--- TRANSCRIPTION START: {audio_path} ---")
            t_start = time.time()
            
            # transcribe is a generator, so we need to iterate or call in thread
            def run_transcription():
                segments, info = model.transcribe(audio_path, beam_size=5, language="ru")
                return list(segments), info

            segments, info = await asyncio.to_thread(run_transcription)
            
            logger.info(f"Segments generated: {len(segments)}. Language: {info.language} ({info.language_probability:.2f})")
            
            full_text = []
            for i, segment in enumerate(segments):
                full_text.append(segment.text)
                if i % 10 == 0 and i > 0:
                    logger.info(f"Processed {i} segments...")
                
            transcription = " ".join(full_text).strip()
            duration_sec = info.duration
            latency_sec = time.time() - t_start
            
            # WITH 9B+ MODELS, WE MUST UNLOAD AFTER EVERY SESSION TO FREE VRAM FOR OLLAMA
            await self._cleanup_memory()
            
            # --- MEMORY STABILITY WAIT ---
            # Wait 2 seconds for GPU driver to settle
            await asyncio.sleep(2)
            
            trace.end_span("transcription", {
                "duration_sec": duration_sec,
                "latency_sec": latency_sec,
                "segments": len(segments),
                "language": info.language
            })
            
            return transcription
        except Exception as e:
            logger.error(f"Local transcription error: {e}")
            trace.log_error("transcription", str(e))
            
            # Check if this is a CUDA-related error when device is cuda
            error_str = str(e).lower()
            if self.device == "cuda" and ("cuda" in error_str or "nvidia" in error_str or "out of memory" in error_str):
                logger.critical(f"GPU failure detected: {e}")
                raise HardwareError(f"Graphics card error: {str(e)}", device="cuda")
            
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
        """Call Ollama API with retry logic for resource recovery using the chat endpoint."""
        result = {"text": None, "latency_ms": 0, "input_tokens": 0, "output_tokens": 0, "messages": messages}
        t_start = time.time()
        
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 4096,
                "num_ctx": 16384,
            }
        }

        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Increased timeout to 900s (15 min) for large context processing
                async with httpx.AsyncClient(timeout=900.0) as client:
                    response = await client.post(f"{self.ollama_url}/api/chat", json=payload)
                    
                    if response.status_code == 200:
                        resp_json = response.json()
                        result["text"] = resp_json.get("message", {}).get("content", "")
                        result["input_tokens"] = resp_json.get("prompt_eval_count", 0)
                        result["output_tokens"] = resp_json.get("eval_count", 0)
                        result["latency_ms"] = int((time.time() - t_start) * 1000)
                        return result
                    
                    if response.status_code == 500 and attempt < max_retries - 1:
                        logger.warning(f"Ollama returned 500 (Attempt {attempt+1}/{max_retries}). Retrying in 5s...")
                        await asyncio.sleep(5)
                        continue
                        
                    response.raise_for_status()
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Ollama Exception: {e} (Attempt {attempt+1}/{max_retries}). Retrying in 5s...")
                    await asyncio.sleep(5)
                    continue
                logger.error(f"Ollama Error: {e}")
                raise
        
        return result

    async def create_protocol(self, transcription: str) -> Dict[str, Any]:
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
            {"role": "system", "content": system_text},
            {"role": "user", "content": f"Внимательно изучи расшифровку и составь подробный протокол НА РУССКОМ ЯЗЫКЕ:\n\n{transcription}"}
        ]
        
        logger.info(f"--- PROTOCOL GENERATION START: {len(transcription)} chars (~{len(transcription)//4} tokens) ---")
        return await self._call_ollama(messages, temperature=0.2)

    async def verify_protocol(self, transcription: str, protocol: str) -> Dict[str, Any]:
        system_text = (
            "Ты — строгий корпоративный аудитор. Твоя задача: Сравнить РАСШИФРОВКУ и готовый ПРОТОКОЛ. \n"
            "ОБЯЗАТЕЛЬНО пиши отчет ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.\n"
            "Найди любые расхождения, пропущенные поручения или фактические ошибки. \n"
            "Выдай краткий отчет на русском языке: что проверено и найдены ли критические ошибки."
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
