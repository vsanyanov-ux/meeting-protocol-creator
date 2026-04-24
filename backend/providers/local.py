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
                 ollama_model: str = "qwen2.5:latest",
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

        # Log specific GPU info if using CUDA
        if self.device == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_name = torch.cuda.get_device_name(0)
                    vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    logger.info(f"--- CUDA DEVICE DETECTED: {gpu_name} ({vram:.1f} GB) ---")
                else:
                    logger.warning("--- CUDA requested but torch.cuda.is_available() is False! ---")
            except Exception as e:
                logger.warning(f"Could not get GPU info: {e}")
            
        # use int8_float16 for stability and speed on RTX cards
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
        if self.device == "cuda":
            await self._unload_ollama_models()
            await self._cleanup_memory()
            
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
                
            transcription = "\n".join(full_text).strip()
            duration_sec = info.duration
            latency_sec = time.time() - t_start
            
            # Free VRAM for Ollama
            # Temporarily disabled to diagnose crash on exit
            # await self._cleanup_memory()
            # await asyncio.sleep(2)
            
            return transcription
        except Exception as e:
            logger.error(f"Local transcription error: {e}")
            trace.log_error("transcription", str(e))
            
            # Check if this is a CUDA-related error when device is cuda
            error_str = str(e).lower()
            if self.device == "cuda" and ("cuda" in error_str or "nvidia" in error_str or "out of memory" in error_str):
                logger.critical(f"GPU failure detected: {e}")
                raise HardwareError(f"Graphics card error: {str(e)}", device="cuda")
            raise e

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

    def _chunk_text(self, text: str, max_chars: int = 15000) -> List[str]:
        """Splits long text into manageable chunks, handling both lines and long blocks."""
        if len(text) <= max_chars:
            return [text]
            
        chunks = []
        lines = text.splitlines(keepends=True)
        current_chunk = []
        current_length = 0
        
        for line in lines:
            # If a single line is too long, we must split it by characters
            if len(line) > max_chars:
                # First, flush current chunk if not empty
                if current_chunk:
                    chunks.append("".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # Split the long line into pieces
                for j in range(0, len(line), max_chars):
                    chunks.append(line[j : j + max_chars])
                continue

            if current_length + len(line) > max_chars and current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = []
                current_length = 0
            
            current_chunk.append(line)
            current_length += len(line)
            
        if current_chunk:
            chunks.append("".join(current_chunk))
            
        return chunks

    async def create_protocol(self, transcription: str, status_updater: Optional[Callable[[str, str], None]] = None, file_id: Optional[str] = None) -> Dict[str, Any]:
        # Define the threshold for chunking (approx 15k chars)
        CHUNK_THRESHOLD = 15000
        
        if len(transcription) <= CHUNK_THRESHOLD:
            # Original logic for short texts
            return await self._create_protocol_single(transcription)
        else:
            # --- PERSISTENCE LOGIC ---
            logger.info(f"LONG TRANSCRIPT DETECTED ({len(transcription)} chars). Using chunked processing...")
            chunks = self._chunk_text(transcription, max_chars=CHUNK_THRESHOLD)
            storage_dir = "storage"
            if not os.path.exists(storage_dir):
                os.makedirs(storage_dir)
            
            storage_path = os.path.join(storage_dir, f"summaries_{file_id}.json") if file_id else None
            
            partial_summaries = []
            start_index = 0
            
            # Load existing progress if available
            if storage_path and os.path.exists(storage_path):
                try:
                    with open(storage_path, "r", encoding="utf-8") as f:
                        saved_data = json.load(f)
                        if saved_data.get("chunks_count") == len(chunks):
                            partial_summaries = saved_data.get("summaries", [])
                            start_index = len(partial_summaries)
                            logger.info(f"RESUMING processing from chunk {start_index + 1}/{len(chunks)}")
                except Exception as e:
                    logger.warning(f"Failed to load persistence data: {e}")
            
            for i in range(start_index, len(chunks)):
                chunk = chunks[i]
                logger.info(f"Processing chunk {i+1}/{len(chunks)}...")
                if status_updater:
                    status_updater("summarizing", f"Анализ части {i+1} из {len(chunks)}...")
                
                summary_part = await self._summarize_chunk(chunk, i+1, len(chunks))
                partial_summaries.append(summary_part)
                
                # Save progress after each chunk
                if storage_path:
                    try:
                        with open(storage_path, "w", encoding="utf-8") as f:
                            json.dump({
                                "chunks_count": len(chunks),
                                "summaries": partial_summaries,
                                "timestamp": time.time()
                            }, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        logger.warning(f"Failed to save persistence data: {e}")
                
            combined_context = "\n\n=== ЧАСТЬ ПРОТОКОЛА ===\n".join(partial_summaries)
            logger.info("Generating final consolidated protocol from partial summaries...")
            if status_updater:
                status_updater("summarizing", "Формирование финального протокола...")
            
            result = await self._create_protocol_single(combined_context, is_consolidated=True)
            
            # Clean up storage on successful completion
            if storage_path and os.path.exists(storage_path):
                try:
                    os.remove(storage_path)
                    logger.info(f"Cleaned up persistence file: {storage_path}")
                except: pass
                
            return result

    async def _summarize_chunk(self, chunk: str, index: int, total: int) -> str:
        """Summarizes a single chunk of transcription into key points."""
        system_text = (
            "Ты — профессиональный секретарь. Твоя задача — выделить все важные факты, решения и поручения "
            f"из части {index} (из {total}) транскрипции совещания. Пиши на РУССКОМ ЯЗЫКЕ.\n"
            "Стиль: максимально плотный, тезисный, без вступлений. Сохраняй все фамилии и цифры."
        )
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": f"ВЫДЕЛИ ГЛАВНОЕ ИЗ ЭТОЙ ЧАСТИ РАСШИФРОВКИ:\n\n{chunk}"}
        ]
        res = await self._call_ollama(messages, temperature=0.1)
        return res.get("text", "Ошибка обработки части.")

    async def _create_protocol_single(self, text: str, is_consolidated: bool = False) -> Dict[str, Any]:
        """Standard protocol generation for a single block of text (or consolidated summaries)."""
        prompt_prefix = "составь подробный протокол" if not is_consolidated else "составь ФИНАЛЬНЫЙ СВОДНЫЙ протокол на основе этих тезисов"
        
        system_text = (
            "Ты — ведущий эксперт по техническому документообороту и промышленному инжинирингу. Твоя задача — составить официальный протокол совещания на основе " + 
            ("тезисов разных частей обсуждения.\n\n" if is_consolidated else "расшифровки.\n\n") +
            "ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:\n"
            "1. ЯЗЫК: ВЕСЬ ответ должен быть СТРОГО на РУССКОМ языке. Использование английского языка ЗАПРЕЩЕНО.\n"
            "2. СОХРАННОСТЬ ДАННЫХ: Обязательно сохраняй технические маркировки, артикулы, названия сплавов, коды изделий.\n"
            "3. ТОЧНОСТЬ: Будь точен в числовых параметрах и единицах измерения.\n"
            "4. ТАБЛИЦА ПОРУЧЕНИЙ: Секцию 'Принятые решения и Поручения' ОБЯЗАТЕЛЬНО оформляй в виде Markdown-таблицы.\n\n"
            "СТРУКТУРА ОТВЕТА:\n"
            "## Общая информация\n"
            "## Участники\n"
            "## Повестка дня\n"
            "## Ход обсуждения\n"
            "## Принятые решения и Поручения\n"
            "| № | Поручение | Ответственный | Срок исполнения |\n"
            "|---|-----------|---------------|------------------|\n\n"
            "## Нерешенные вопросы\n\n"
            "ПИШИ ТОЛЬКО НА РУССКОМ. БУДЬ ЛАКОНИЧНЫМ И СТРОГИМ."
        )
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": f"Внимательно изучи {'тезисы' if is_consolidated else 'расшифровку'} и {prompt_prefix} НА РУССКОМ ЯЗЫКЕ:\n\n{text}"}
        ]
        
        logger.info(f"--- FINAL PROTOCOL GENERATION START: {len(text)} chars ---")
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
