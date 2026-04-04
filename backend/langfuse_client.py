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
from typing import Optional, Any
from loguru import logger

# Глобальный инстанс Langfuse (создаётся один раз)
_langfuse_instance = None
_langfuse_enabled = None  # None = ещё не проверяли


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

    Использование:
        trace = PipelineTrace(file_id, filename="meeting.mp3")
        with trace.span("transcription"):
            ...
        trace.log_generation(input_text, output_text, model, latency_ms)
        trace.score("user_rating", 4.0)
        trace.finish(status="completed")
    """

    def __init__(self, file_id: str, filename: str = "", provider: str = "yandex"):
        self.file_id = file_id
        self.lf = get_langfuse()
        self._trace = None
        self._active_spans: dict = {}

        if self.lf:
            try:
                self._trace = self.lf.trace(
                    id=file_id,
                    name="meeting_protocol_pipeline",
                    input={"filename": filename, "provider": provider},
                    metadata={
                        "file_id": file_id,
                        "provider": provider,
                    },
                    tags=["meeting-protocol", provider]
                )
            except Exception as e:
                logger.error(f"Langfuse trace creation error: {e}")

    def start_span(self, name: str, input_data: dict = None) -> Optional[Any]:
        """Начинает именованный span (этап pipeline)."""
        if not self._trace:
            return None
        try:
            span = self._trace.span(
                name=name,
                input=input_data or {},
                start_time=__import__("datetime").datetime.utcnow()
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

    def log_generation(
        self,
        input_messages: list,
        output_text: str,
        model: str = "yandexgpt/latest",
        latency_ms: int = 0,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ):
        """
        Логирует LLM-вызов как Generation в Langfuse.
        Именно это появится во вкладке 'Generations' в UI.
        """
        if not self._trace:
            return
        try:
            usage = {}
            if input_tokens:
                usage["input"] = input_tokens
            if output_tokens:
                usage["output"] = output_tokens
            if input_tokens and output_tokens:
                usage["total"] = input_tokens + output_tokens

            self._trace.generation(
                name="create_protocol",
                model=model,
                model_parameters={"temperature": 0.3, "max_tokens": 2000},
                input=input_messages,
                output=output_text,
                usage=usage if usage else None,
                metadata={"latency_ms": latency_ms}
            )
        except Exception as e:
            logger.error(f"Langfuse generation log error: {e}")

    def score(self, name: str, value: float, comment: str = ""):
        """
        Добавляет оценку к трейсу.
        name: 'user_rating', 'protocol_completeness', 'formatting_quality'
        value: 0.0 - 1.0 (или любая числовая шкала)
        """
        if not self.lf or not self._trace:
            return
        try:
            self.lf.score(
                trace_id=self.file_id,
                name=name,
                value=value,
                comment=comment
            )
        except Exception as e:
            logger.error(f"Langfuse score error: {e}")

    def finish(self, status: str = "completed", output: dict = None):
        """Завершает trace с итоговым статусом."""
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
