"""
Langfuse LLM Observability Client
----------------------------------
Опциональный модуль. Если LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
не заданы в .env — все функции работают как no-op (ничего не делают).

Что трекается:
  - Trace      — весь pipeline для одного file_id
  - Span        — этапы: transcription, docx_generation, email
  - Generation  — LLM вызов: input (транскрипция) + output (протокол) + latency
  - Score       — пользовательская оценка качества (1-5)
"""

import os
import time
import datetime
from typing import Optional, Any, Dict
from loguru import logger

# Глобальный инстанс Langfuse (создаётся один раз)
_langfuse_instance = None
_langfuse_enabled = None  # None = ещё не проверяли


# Тарифы Yandex Cloud (в USD, по курсу ~78 RUB)
YANDEX_PRICING = {
    "yandexgpt": (1.2 / 1000) / 78,      # ~$0.0000153 за токен
    "speechkit_stt": (0.6 / 60) / 78,    # ~$0.000128 за секунду
}

def get_langfuse() -> Optional[Any]:
    """Возвращает Langfuse клиент или None если не сконфигурирован."""
    global _langfuse_instance, _langfuse_enabled

    if _langfuse_enabled is False:
        return None
    if _langfuse_instance is not None:
        return _langfuse_instance

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        logger.info("Langfuse не сконфигурирован (LANGFUSE_PUBLIC_KEY/SECRET_KEY отсутствуют). Трекинг отключён.")
        _langfuse_enabled = False
        return None

    try:
        from langfuse import Langfuse
        _langfuse_instance = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host
        )
        _langfuse_enabled = True
        logger.info(f"✅ Langfuse подключён: {host}")
        return _langfuse_instance
    except ImportError:
        logger.warning("langfuse не установлен. Запустите: pip install langfuse")
        _langfuse_enabled = False
        return None
    except Exception as e:
        logger.error(f"Ошибка инициализации Langfuse: {e}")
        _langfuse_enabled = False
        return None


class PipelineTrace:
    """
    Обёртка над Langfuse Trace для одного pipeline-вызова.
    """

    def __init__(self, file_id: str, filename: str = "", provider: str = "yandex", metadata: dict = None):
        self.file_id = file_id
        self.lf = get_langfuse()
        self._trace = None
        self._active_spans: dict = {}
        self._observations: Dict[str, Any] = {}

        if self.lf:
            try:
                # Базовые метаданные трейса
                trace_metadata = {
                    "file_id": file_id,
                    "provider": provider
                }
                if metadata:
                    trace_metadata.update(metadata)

                # Делаем ID трейса уникальным для каждого запуска, чтобы избежать склейки в Langfuse
                from datetime import datetime
                actual_trace_id = f"{file_id}_{datetime.now().strftime('%H%M%S')}"
                
                logger.info(f"🚀 Starting Langfuse trace: {actual_trace_id} (original file: {file_id})")
                
                self.trace_id = actual_trace_id
                self._trace = self.lf.trace(
                    id=actual_trace_id,
                    name="meeting_protocol_processing",
                    user_id="anonymous",
                    metadata={
                        "filename": filename,
                        "provider": provider,
                        "file_id": file_id,
                        **(metadata or {})
                    },
                    tags=["meeting-protocol", provider]
                )
            except Exception as e:
                logger.error(f"Langfuse trace creation error: {e}")
                self.trace_id = file_id # Fallback
        else:
            self.trace_id = file_id

    def start_span(self, name: str, input_data: dict = None) -> Optional[Any]:
        """Начинает именованный span (этап pipeline)."""
        if not self._trace:
            return None
        try:
            span = self._trace.span(
                name=name,
                input=input_data or {},
                start_time=datetime.datetime.utcnow()
            )
            self._active_spans[name] = span
            return span
        except Exception as e:
            logger.error(f"Langfuse span error ({name}): {e}")
            return None

    def end_span(self, name: str, output_data: dict = None, level: str = "DEFAULT"):
        """Завершает именованный span."""
        span = self._active_spans.pop(name, None)
        if span:
            try:
                span.end(output=output_data or {}, level=level)
            except Exception as e:
                logger.error(f"Langfuse span end error ({name}): {e}")

    def log_error(self, stage: str, message: str, error_details: str = None):
        """Логирует ошибку в трейс."""
        if not self._trace:
            return
        try:
            self._trace.event(
                name=f"error_{stage}",
                level="ERROR",
                status_message=message,
                metadata={"error_details": error_details, "stage": stage}
            )
        except Exception as e:
            logger.error(f"Langfuse log_error error: {e}")

    def log_generation(
        self,
        input_messages: list,
        output_text: str,
        model: str = "yandexgpt/latest",
        latency_ms: int = 0,
        input_tokens: Any = None,
        output_tokens: Any = None,
    ):
        """Логирует LLM-вызов с расчетом стоимости в USD."""
        if not self._trace:
            return
        try:
            # Принудительно приводим к числу, так как Yandex может вернуть неожиданные типы
            i_tokens = int(input_tokens) if input_tokens is not None else 0
            o_tokens = int(output_tokens) if output_tokens is not None else 0
            total_tokens = i_tokens + o_tokens
            
            # Расчет стоимости
            cost = (i_tokens * YANDEX_PRICING["yandexgpt"]) + (o_tokens * YANDEX_PRICING["yandexgpt"])
            usage = {"input": i_tokens, "output": o_tokens, "total": total_tokens}
            
            # Calculate startTime and endTime for proper latency reporting in dashbord
            end_time = datetime.datetime.now()
            start_time = end_time - datetime.timedelta(milliseconds=latency_ms)
            
            gen_name = "create_protocol" if "auditor" not in model else "audit_protocol"

            gen = self._trace.generation(
                name=gen_name,
                model=model,
                model_parameters={"temperature": 0.3},
                input=input_messages,
                output=output_text,
                usage=usage,
                cost=cost if cost > 0 else None,
                start_time=start_time,
                end_time=end_time,
                metadata={
                    "calculated_cost_usd": cost 
                }
            )
            self._observations[gen_name] = gen
            
            logger.info(f"📊 Langfuse Log Generation: name={gen_name}, model={model}, tokens={total_tokens}, cost=${cost:.6f}")
            
            # Аккумулируем общую стоимость трейса и обновляем его
            if not hasattr(self, 'total_cost'):
                self.total_cost = 0.0
            self.total_cost += cost
            self._trace.update(total_cost=self.total_cost)
            
            self.lf.flush() # Принудительно отправляем данные
        except Exception as e:
            logger.error(f"❌ Langfuse generation log error: {e} (tokens: {input_tokens}/{output_tokens})")

    def log_stt(self, duration_sec: Any, model: str = "speechkit-stt"):
        """Логирует транскрибацию с расчетом стоимости по времени в USD."""
        if not self._trace:
            return
        try:
            d_sec = float(duration_sec) if duration_sec is not None else 0.0
            cost = float(d_sec * YANDEX_PRICING["speechkit_stt"])
            
            logger.info(f"📊 Langfuse Log STT: duration={d_sec}s, cost=${cost:.6f}")

            self._trace.generation(
                name="transcription",
                model=model,
                output="[Audio Transcription]",
                usage={"unit": "seconds", "input": int(d_sec)},
                cost=cost if cost > 0 else None,
                metadata={
                    "duration_sec": d_sec,
                    "calculated_cost_usd": cost
                }
            )
            self.lf.flush()
        except Exception as e:
            logger.error(f"Langfuse STT log error: {e}")

    def score(self, name: str, value: float, comment: Optional[str] = None):
        """Логирует оценку (score) для трейса. Пытается привязать к аудитору или генерации."""
        if not self._trace:
            return
        try:
            # Определяем, к чему привязывать оценку
            # Если это AI-оценка, пробуем привязать к audit_protocol или create_protocol
            target = self._trace
            if name.startswith("ai_"):
                if "audit_protocol" in self._observations:
                    target = self._observations["audit_protocol"]
                elif "create_protocol" in self._observations:
                    target = self._observations["create_protocol"]

            target.score(
                name=name,
                value=value,
                comment=comment
            )
            logger.info(f"🎯 Langfuse Score Logged on {target.name if hasattr(target, 'name') else 'trace'}: {name}={value}")
            self.lf.flush() # Принудительно отправляем оценку
        except Exception as e:
            logger.error(f"Langfuse score error: {e}")

    def finish(self, status: str = "completed", output: dict = None):
        """Завершает trace."""
        if not self._trace:
            return
        try:
            self._trace.update(
                output=output or {"status": status},
                metadata={"final_status": status}
            )
            if self.lf:
                self.lf.flush()
        except Exception as e:
            logger.error(f"Langfuse trace finish error: {e}")


def submit_score(file_id: str, score_name: str, value: float, comment: str = "") -> bool:
    """
    Отправить оценку в Langfuse по file_id.
    Вызывается из /feedback endpoint.
    """
    lf = get_langfuse()
    if not lf:
        return False
    try:
        lf.score(
            trace_id=file_id,
            name=score_name,
            value=value,
            comment=comment
        )
        lf.flush()
        return True
    except Exception as e:
        logger.error(f"Langfuse submit_score error: {e}")
        return False
