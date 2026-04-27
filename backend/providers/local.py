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
import torchaudio
from faster_whisper import WhisperModel
import ollama

from .base import BaseAIProvider
from exceptions import HardwareError
from langfuse_client import get_prompt

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
        if self.device == "cuda":
            await self._unload_ollama_models()
            await self._cleanup_memory()
            
        status_updater("transcribing", f"Loading Whisper ({self.whisper_model_size})...")
        
        trace.start_span("transcription")
        try:
            model = await self._get_whisper()
            
            status_updater("transcribing", f"Processing via Local Whisper ({self.whisper_model_size})...")
            logger.info(f"--- TRANSCRIPTION START: {audio_path} ---")
            t_start = time.time()
            
            def run_transcription():
                segments, info = model.transcribe(audio_path, beam_size=5, language="ru")
                return list(segments), info

            segments, info = await asyncio.to_thread(run_transcription)
            logger.info(f"Segments generated: {len(segments)}. Language: {info.language}")
            
            full_text = []
            for i, segment in enumerate(segments):
                # Generate timestamp for every segment
                timestamp = f"[{int(segment.start // 60):02d}:{int(segment.start % 60):02d}]"
                full_text.append(f"{timestamp} {segment.text.strip()}")
                
                if i % 10 == 0 and i > 0:
                    status_updater("transcribing", f"Обработано {i} фрагментов речи...")
                
            transcription = "\n".join(full_text).strip()
            
            
            return transcription
        except Exception as e:
            logger.error(f"Local transcription error: {e}")
            trace.log_error("transcription", str(e))
            raise e

    async def _ensure_model_exists(self, client: ollama.Client):
        if self._model_verified:
            return
        
        try:
            logger.info(f"Checking if Ollama model '{self.ollama_model}' is available...")
            response = await asyncio.to_thread(client.list)
            model_names = [m.model for m in response.models]
            
            if self.ollama_model not in model_names and (self.ollama_model + ":latest") not in model_names:
                logger.info(f"Model '{self.ollama_model}' not found. Pulling it now...")
                await asyncio.to_thread(client.pull, self.ollama_model)
                logger.info(f"Model '{self.ollama_model}' pulled successfully.")
            
            self._model_verified = True
        except Exception as e:
            logger.error(f"Failed to verify/pull Ollama model: {e}")

    async def _call_ollama(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> Dict[str, Any]:
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
                        await asyncio.sleep(5)
                        continue
                        
                    response.raise_for_status()
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                    continue
                raise
        
        return result

    def _chunk_text(self, text: str, max_chars: int = 15000) -> List[str]:
        if len(text) <= max_chars:
            return [text]
            
        chunks = []
        lines = text.splitlines(keepends=True)
        current_chunk = []
        current_length = 0
        
        for line in lines:
            if len(line) > max_chars:
                if current_chunk:
                    chunks.append("".join(current_chunk))
                    current_chunk = []
                    current_length = 0
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
        CHUNK_THRESHOLD = 15000
        if len(transcription) <= CHUNK_THRESHOLD:
            return await self._create_protocol_single(transcription)
        else:
            logger.info(f"LONG TRANSCRIPT DETECTED. Using chunked processing...")
            chunks = self._chunk_text(transcription, max_chars=CHUNK_THRESHOLD)
            storage_dir = "storage"
            if not os.path.exists(storage_dir):
                os.makedirs(storage_dir)
            
            storage_path = os.path.join(storage_dir, f"summaries_{file_id}.json") if file_id else None
            partial_summaries = []
            start_index = 0
            
            if storage_path and os.path.exists(storage_path):
                try:
                    with open(storage_path, "r", encoding="utf-8") as f:
                        saved_data = json.load(f)
                        if saved_data.get("chunks_count") == len(chunks):
                            partial_summaries = saved_data.get("summaries", [])
                            start_index = len(partial_summaries)
                except Exception as e:
                    logger.warning(f"Failed to load persistence data: {e}")
            
            for i in range(start_index, len(chunks)):
                chunk = chunks[i]
                if status_updater:
                    status_updater("summarizing", f"Анализ части {i+1} из {len(chunks)}...")
                summary_part = await self._summarize_chunk(chunk, i+1, len(chunks))
                partial_summaries.append(summary_part)
                if storage_path:
                    with open(storage_path, "w", encoding="utf-8") as f:
                        json.dump({"chunks_count": len(chunks), "summaries": partial_summaries}, f, ensure_ascii=False)
                
            combined_context = "\n\n=== ЧАСТЬ ПРОТОКОЛА ===\n".join(partial_summaries)
            if status_updater:
                status_updater("summarizing", "Формирование финального протокола...")
            
            result = await self._create_protocol_single(combined_context, is_consolidated=True)
            if storage_path and os.path.exists(storage_path):
                try: os.remove(storage_path)
                except: pass
            return result

    async def _summarize_chunk(self, chunk: str, index: int, total: int) -> str:
        fallback_system = (
            "Ты — профессиональный секретарь и эксперт по анализу деловых встреч. Твоя задача — выделить все важные факты, решения и поручения "
            f"из части {index} (из {total}) транскрипции совещания. Пиши на РУССКОМ ЯЗЫКЕ.\n"
            "Стиль: максимально плотный, тезисный, без вступлений. Сохраняй все имена, цифры и ключевые термины."
        )
        system_text = get_prompt("meeting_summarize_chunk", fallback=fallback_system)
        
        # Если промт из Langfuse, он может содержать {{index}} и {{total}}
        if "{{" in system_text:
            system_text = system_text.replace("{{index}}", str(index)).replace("{{total}}", str(total))

        user_prompt = get_prompt("meeting_summarize_chunk_user", fallback="ВЫДЕЛИ ГЛАВНОЕ:\n\n{{chunk}}")
        user_text = user_prompt.replace("{{chunk}}", chunk)

        messages = [{"role": "system", "content": system_text}, {"role": "user", "content": user_text}]
        res = await self._call_ollama(messages, temperature=0.1)
        return res.get("text", "Ошибка обработки части.")

    async def _create_protocol_single(self, text: str, is_consolidated: bool = False) -> Dict[str, Any]:
        prompt_prefix = "составь подробный протокол" if not is_consolidated else "составь ФИНАЛЬНЫЙ СВОДНЫЙ протокол"
        source_type = "расшифровки" if not is_consolidated else "тезисов"
        
        fallback_system = (
            "Ты — профессиональный специалист по ведению протоколов совещаний. Твоя задача — составить официальный протокол на основе " + 
            ("тезисов.\n\n" if is_consolidated else "расшифровки.\n\n") +
            "1. ЯЗЫК: СТРОГО РУССКИЙ.\n2. ТОЧНОСТЬ: Сохраняй все важные детали, имена, даты и цифры. Не выдумывай факты, которых нет в тексте.\n"
            "## Общая информация\n## Участники\n## Повестка дня\n## Ход обсуждения\n## Принятые решения и Поручения\n"
            "| № | Поручение | Ответственный | Срок исполнения |\n|---|-----------|---------------|------------------|\n\n## Нерешенные вопросы"
        )
        
        system_text = get_prompt("meeting_create_protocol", fallback=fallback_system)
        
        user_prompt = get_prompt("meeting_create_protocol_user", fallback=f"Изучи текст и {prompt_prefix} НА РУССКОМ:\n\n{{text}}")
        user_text = user_prompt.replace("{{text}}", text)\
                               .replace("{{source_type}}", source_type)\
                               .replace("{{action_type}}", prompt_prefix)

        messages = [{"role": "system", "content": system_text}, {"role": "user", "content": user_text}]
        return await self._call_ollama(messages, temperature=0.2)

    async def verify_protocol(self, transcription: str, protocol: str) -> Dict[str, Any]:
        fallback_system = "Ты — корпоративный аудитор. Сравни РАСШИФРОВКУ и ПРОТОКОЛ. Выдай краткий отчет на русском."
        system_text = get_prompt("meeting_verify_protocol", fallback=fallback_system)
        
        user_prompt = get_prompt("meeting_verify_protocol_user", fallback="РАСШИФРОВКА:\n{{transcription}}\n\nПРОТОКОЛ:\n{{protocol}}")
        user_text = user_prompt.replace("{{transcription}}", transcription).replace("{{protocol}}", protocol)
        
        messages = [{"role": "system", "content": system_text}, {"role": "user", "content": user_text}]
        res = await self._call_ollama(messages, temperature=0.1)
        
        text = res.get("text", "")
        scores = {}
        
        # Попытка извлечь JSON с оценками
        import re
        try:
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
            if json_match:
                score_data = json.loads(json_match.group(1))
                scores = score_data.get("scores", {})
                logger.info(f"✅ Auditor scores extracted (local): {scores}")
        except Exception as je:
            logger.warning(f"Could not parse auditor scores (local): {je}")

        # Очистка текста от JSON и технических заголовков для пользователя
        clean_report = re.sub(r"```json\s*\{.*?\}\s*```", "", text, flags=re.DOTALL)
        clean_report = re.sub(r"###?\s*JSON.*?\n", "", clean_report, flags=re.IGNORECASE)
        
        return {
            "verification_report": clean_report.strip() or "Ошибка верификации", 
            "input_tokens": res["input_tokens"], 
            "output_tokens": res["output_tokens"],
            "scores": scores
        }

