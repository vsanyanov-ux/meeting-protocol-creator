"""
Langfuse LLM Observability Client
----------------------------------
Оптимизирован для SDK v4.0.6. Использует ручную привязку через trace_context.
"""

import os
import time
import datetime
import uuid
from typing import Optional, Any, Dict, Union
from loguru import logger
from langfuse import propagate_attributes

# Глобальный инстанс Langfuse
_langfuse_instance = None
_langfuse_enabled = None

# Тарифы Yandex Cloud (в USD, по курсу ~80 RUB)
YANDEX_PRICING = {
    "yandexgpt": (1.2 / 1000) / 80,      # ~$0.0000130 за токен
    "speechkit_stt": (0.6 / 60) / 80,    # ~$0.000108 за секунду
}

def get_langfuse() -> Optional[Any]:
    global _langfuse_instance, _langfuse_enabled
    if _langfuse_enabled is False: return None
    if _langfuse_instance is not None: return _langfuse_instance

    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not pk or not sk:
        _langfuse_enabled = False
        return None

    try:
        from langfuse import Langfuse
        
        _langfuse_instance = Langfuse(
            public_key=pk, 
            secret_key=sk, 
            host=host
        )
        _langfuse_enabled = True
        return _langfuse_instance
    except Exception as e:
        logger.error(f"Langfuse init error: {e}")
        _langfuse_enabled = False
        return None


class PipelineTrace:
    """
    Обёртка над Langfuse для SDK v4.0.6.
    Разделяет Trace ID (32 hex) и Span ID (16 hex) для соответствия валидации SDK.
    """

    def __init__(self, file_id: str, filename: str = "", provider: str = "yandex", metadata: dict = None, session_id: str = None):
        self.file_id = file_id
        self.filename = filename
        self.provider = provider
        self.metadata = metadata or {}
        self.session_id = session_id
        self.lf = get_langfuse()
        
        # Langfuse v4 OTel needs hex IDs (32 chars for trace, 16 for span)
        # Using a proper trace_id format ensures stability across the SDK
        self.trace_id = file_id.replace("-", "") if file_id else uuid.uuid4().hex
        if len(self.trace_id) < 32:
            self.trace_id = (self.trace_id * 32)[:32]
        elif len(self.trace_id) > 32:
            self.trace_id = self.trace_id[:32]
            
        self._trace_obj = None
        self._root_obs = None
        self._prop_ctx = None
        self._active_spans = {}
        self.total_cost = 0.0

    def __enter__(self):
        if not self.lf: return self
        try:
            # 1. Используем официальный метод проброса атрибутов трейса для SDK v4.
            # Это устанавливает контекст для всех последующих OTel операций.
            self._prop_ctx = propagate_attributes(
                session_id=self.session_id,
                user_id=self.metadata.get("email"),
                metadata=self.metadata,
                tags=["meeting-protocol", self.provider]
            )
            self._prop_ctx.__enter__()

            # 2. СОЗДАЕМ ТРЕЙС ЧЕРЕЗ LOW-LEVEL API.
            # Это ГАРАНТИРУЕТ, что sessionId и userId будут на верхнем уровне JSON,
            # что критично для появления данных в разделе Sessions в Langfuse UI.
            try:
                self.lf.api.ingestion.batch(
                    batch=[{
                        "id": uuid.uuid4().hex,
                        "type": "trace-create",
                        "timestamp": datetime.datetime.now().isoformat() + "Z",
                        "body": {
                            "id": self.trace_id,
                            "name": "meeting_protocol_processing",
                            "sessionId": self.session_id,
                            "userId": self.metadata.get("email"),
                            "metadata": {
                                **self.metadata,
                                "file_id": self.file_id,
                                "filename": self.filename
                            },
                            "tags": ["meeting-protocol", self.provider]
                        }
                    }]
                )
            except Exception as le:
                logger.debug(f"Low-level trace creation failed: {le}")

            # 3. Начинаем корневой span через start_as_current_observation.
            # Он автоматически привяжется к нашему trace_id из OTel контекста.
            self._root_obs_ctx = self.lf.start_as_current_observation(
                name="meeting_protocol_processing",
                as_type="span",
                trace_context={"trace_id": self.trace_id},
                input={"filename": self.filename, "provider": self.provider},
                end_on_exit=False
            )
            self._root_obs = self._root_obs_ctx.__enter__()

            logger.info(f"Started Langfuse v4 trace: {self.trace_id} (Session: {self.session_id})")
            return self
        except Exception as e:
            import traceback
            logger.error(f"Langfuse v4 start error: {e}\n{traceback.format_exc()}")
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.log_error("exception", str(exc_val))
        
        # Завершаем трейс автоматически, если он еще не был завершен вручную
        self.finish(status="error" if exc_type else "completed")

        # Завершаем контекст корневого наблюдения
        if hasattr(self, "_root_obs_ctx") and self._root_obs_ctx:
            try:
                self._root_obs_ctx.__exit__(exc_type, exc_val, exc_tb)
            except:
                pass

        # Завершаем контекст проброса атрибутов
        if self._prop_ctx:
            try:
                self._prop_ctx.__exit__(exc_type, exc_val, exc_tb)
            except:
                pass
        
        if self.lf:
            self.lf.flush()

    def _get_context(self):
        """Возвращает контекст для привязки к родителю."""
        return {
            "trace_id": self.trace_id,
            "parent_observation_id": self._root_obs.id if self._root_obs else None
        }

    def start_span(self, name: str, input_data: dict = None, as_type: str = "span") -> Optional[Any]:
        if not self.lf or not self._root_obs: return None
        try:
            # В SDK v4 для надежной привязки используем lf.start_observation с trace_context
            span = self.lf.start_observation(
                name=name,
                as_type=as_type,
                trace_context={
                    "trace_id": self.trace_id,
                    "parent_span_id": self._root_obs.id
                },
                input=input_data
            )
            # ВАЖНО: Добавляем в список активных спанов для последующего закрытия/обновления
            self._active_spans[name] = span
            return span
        except Exception as e:
            logger.error(f"Langfuse start_span error: {e}")
            return None

    def end_span(self, name: str, output_data: dict = None, level: str = "DEFAULT"):
        span = self._active_spans.pop(name, None)
        if span:
            try:
                span.update(output=output_data, level=level)
                span.end()
                # Принудительно пушим данные для коротких этапов
                self.lf.flush()
            except Exception as e:
                logger.error(f"Langfuse span end error ({name}): {e}")

    def log_generation(
        self,
        input_messages: list,
        output_text: str,
        model: str = "yandexgpt/latest",
        latency_ms: int = 0,
        input_tokens: Any = None,
        output_tokens: Any = None,
        name: Optional[str] = None
    ):
        if not self.lf or not self._root_obs: return
        try:
            i_t = int(input_tokens) if input_tokens is not None else 0
            o_t = int(output_tokens) if output_tokens is not None else 0
            
            price_per_token = YANDEX_PRICING.get("yandexgpt", 0)
            if "gpt" not in model.lower() and "llama" not in model.lower():
                price_per_token = 0

            cost = (i_t + o_t) * price_per_token
            usage = {"input": i_t, "output": o_t, "total": i_t + o_t}
            
            sanitized_messages = []
            for m in input_messages:
                new_m = m.copy()
                if "text" in new_m and "content" not in new_m:
                    new_m["content"] = new_m.pop("text")
                sanitized_messages.append(new_m)

            if name:
                gen_name = name
            elif "auditor" in model.lower() or "audit" in model.lower():
                gen_name = "Audit Protocol"
            elif "format" in model.lower():
                gen_name = "Format Transcript"
            else:
                gen_name = "Create Protocol"

            # Пытаемся найти активный спан с таким же именем, чтобы сохранить latency
            # Если спана нет, создаем новый "fire and forget"
            gen = self._active_spans.get(gen_name)
            
            if gen:
                # Если это был обычный span, мы не можем сменить тип, 
                # но мы можем обновить его данными генерации
                gen.update(
                    model=model,
                    input=sanitized_messages,
                    output=output_text,
                    usage_details={"input": i_t, "output": o_t, "total": i_t + o_t},
                    cost_details={"total": cost},
                    session_id=self.session_id,
                    sessionId=self.session_id
                )
                # Мы не закрываем его здесь, так как main.py вызовет trace.end_span()
            else:
                # В SDK v4 для гарантии привязки используем lf.start_observation с trace_context
                start_t = datetime.datetime.now() - datetime.timedelta(milliseconds=latency_ms)
                gen = self.lf.start_observation(
                    name=gen_name,
                    as_type="generation",
                    trace_context={
                        "trace_id": self.trace_id,
                        "parent_span_id": self._root_obs.id
                    },
                    model=model,
                    input=sanitized_messages,
                    usage_details=usage,
                    cost_details={"total": cost},
                    completion_start_time=start_t
                )
                gen.update(
                    output=output_text,
                    session_id=self.session_id,
                    sessionId=self.session_id
                )
                gen.end()
            
            self.total_cost += cost
            self.lf.flush()
        except Exception as e:
            logger.error(f"Langfuse generation log error: {e}")

    def log_stt(self, duration_sec: Any, model: str = "speechkit-stt"):
        if not self.lf or not self._root_obs: return
        try:
            d_sec = float(duration_sec) if duration_sec is not None else 0.0
            cost = float(d_sec * YANDEX_PRICING["speechkit_stt"])
            
            # Пытаемся найти активный спан 'transcription'
            gen = self._active_spans.get("transcription")
            
            if gen:
                gen.update(
                    model=model,
                    input={"duration_sec": d_sec},
                    output="[Audio Transcription]",
                    usage_details={"unit": "SECONDS", "input": int(d_sec), "total": int(d_sec)},
                    cost_details={"total": cost},
                    session_id=self.session_id,
                    sessionId=self.session_id
                )
                # Мы не закрываем его здесь, так как main.py вызовет trace.end_span()
            else:
                # В SDK v4 для гарантии привязки используем lf.start_observation с trace_context
                gen = self.lf.start_observation(
                    name="transcription",
                    as_type="generation",
                    trace_context={
                        "trace_id": self.trace_id,
                        "parent_span_id": self._root_obs.id
                    },
                    model=model,
                    input={"duration_sec": d_sec},
                    usage_details={"unit": "SECONDS", "input": int(d_sec)},
                    cost_details={"total": cost}
                )
                gen.update(
                    output="[Audio Transcription]",
                    session_id=self.session_id,
                    sessionId=self.session_id
                )
                gen.end()
            
            self.total_cost += cost
            self.lf.flush()
        except Exception as e:
            logger.error(f"Langfuse STT log error: {e}")

    def score(self, name: str, value: float, comment: Optional[str] = None):
        if not self.lf or not self._root_obs: return
        try:
            # Скоррим корневой СПАН вместо Трейса напрямую. 
            # Это лучше структурирует данные в интерфейсе Langfuse и помогает с именованием.
            self._root_obs.score(name=name, value=value, comment=comment)
            self.lf.flush()
        except Exception as e:
            logger.debug(f"Langfuse Scoring Error: {e}")

    def log_error(self, stage: str, message: str, traceback_str: str = None):
        if not self.lf or not self._root_obs: return
        try:
            err = self._root_obs.start_observation(
                name=f"error_{stage}",
                as_type="span",
                level="ERROR",
                status_message=message,
                metadata={"traceback": traceback_str}
            )
            err.end()
            self.lf.flush()
            logger.error(f"Logged error to Langfuse: {stage} - {message}")
        except Exception as e:
            logger.error(f"Langfuse log_error failed: {e}")



    def finish(self, status: str = "completed", output: dict = None, level: Optional[str] = None):
        if not self.lf or not self._root_obs: return
        # Защита от двойного завершения
        if hasattr(self, "_finished") and self._finished: return
        
        try:
            # Закрываем все висящие спаны
            for name, span in list(self._active_spans.items()):
                try:
                    span.end()
                    logger.debug(f"Auto-closed hanging span: {name}")
                except:
                    pass
            self._active_spans.clear()

            res = output or {"status": status}
            
            # Обновляем корневой спан
            # Если level не передан, определяем его по статусу (completed -> INFO, остальное -> ERROR)
            final_level = level or ("INFO" if status == "completed" else "ERROR")
            
            self._root_obs.update(
                output=res, 
                cost_details={"total": self.total_cost},
                level=final_level
            )
            self._root_obs.end()
            
            self.lf.flush()
            self._finished = True
            logger.info(f"Langfuse Trace Finished: {self.trace_id} (Total Cost: ${self.total_cost:.6f})")
        except Exception as e:
            logger.error(f"Langfuse trace finish error: {e}")

    def get_prompt(self, name: str, tag: str = "latest", type: str = "text") -> Optional[Any]:
        """
        Получить промт из Langfuse. 
        Позволяет управлять версиями промтов через Dashboard.
        """
        if not self.lf: return None
        try:
            # В SDK v4.0.6 параметр называется 'label' вместо 'tag'
            return self.lf.get_prompt(name, label=tag, type=type)
        except Exception as e:
            logger.error(f"Langfuse get_prompt error ({name}): {e}")
            return None


def submit_score(file_id: str, score_name: str, value: float, comment: str = "") -> bool:
    lf = get_langfuse()
    if not lf: return False
    try:
        # Очищаем ID от дефисов для v4 SDK
        clean_id = file_id.replace("-", "")[:32]
        lf.create_score(trace_id=clean_id, name=score_name, value=value, comment=comment)
        lf.flush()
        return True
    except Exception as e:
        logger.error(f"Langfuse submit_score error: {e}")
        return False


def get_prompt(name: str, tag: str = "latest", fallback: str = "") -> str:
    """
    Глобальная функция для получения текста промта. 
    Если Langfuse не настроен или промт не найден, возвращает fallback.
    """
    lf = get_langfuse()
    if not lf: return fallback
    try:
        # В SDK v4.0.6 параметр называется 'label' вместо 'tag'
        prompt_obj = lf.get_prompt(name, label=tag)
        return prompt_obj.prompt
    except Exception as e:
        logger.debug(f"Langfuse prompt '{name}' not found, using fallback. Error: {e}")
        return fallback
