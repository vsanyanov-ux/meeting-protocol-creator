"""
ADK Agent Runtime & Cognitive Loop Engine.
Separates Session Context from Business State and orchestrates tools via ADK contracts.
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, List
from pydantic import BaseModel, Field
from loguru import logger

from core.tools import execute_tool_call


# ============================================================================
# 1. State & Memory Separation Models
# ============================================================================

class SessionContext(BaseModel):
    """Сессионная память: контекст диалога и метаданные обращения."""
    session_id: str = Field(..., description="Идентификатор сессии пользователя")
    user_id: Optional[str] = Field(None, description="Идентификатор пользователя или сервисного аккаунта")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MeetingState(BaseModel):
    """
    Бизнес-состояние задачи (State):
    Структурированные артефакты совещания, статус, аудит и решения.
    """
    file_id: str
    filename: str
    status: str = "starting"
    progress_message: str = "Инициализация агента..."
    
    # Файлы и медиа
    local_path: Optional[str] = None
    normalized_path: Optional[str] = None
    media_type: Optional[str] = None
    
    # Текстовые артефакты
    raw_transcription: Optional[str] = None
    refined_transcription: Optional[str] = None
    protocol_markdown: Optional[str] = None
    docx_path: Optional[str] = None
    
    # Результаты аудита качества
    verification_report: Optional[str] = None
    scores: Dict[str, Any] = Field(default_factory=dict)
    
    # Approval Gate & Dispatch
    recipient_email: Optional[str] = None
    should_send_email: bool = True
    email_approved: bool = False
    email_sent: bool = False
    
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_persistence_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для сохранения в SQLite."""
        return {
            "status": self.status,
            "message": self.progress_message,
            "filename": self.filename,
            "transcription": self.refined_transcription or self.raw_transcription,
            "protocol": self.protocol_markdown,
            "verification_report": self.verification_report,
            "scores": self.scores,
            "docx_path": self.docx_path,
            "recipient_email": self.recipient_email,
            "email_approved": self.email_approved,
            "email_sent": self.email_sent,
        }


# ============================================================================
# 2. ADK Agent Runner (Cognitive Loop)
# ============================================================================

class ADKAgentRunner:
    """
    Автономный агентный исполнитель (ADK Runner) для генерации и аудита протоколов.
    Оркестрирует инструменты через строгие контракты и хуки безопасности.
    """

    def __init__(
        self, 
        ai_provider: Any, 
        status_manager: Any, 
        gpu_lock: Any, 
        processing_semaphore: Any,
        global_pipeline_lock: Any
    ):
        self.ai_provider = ai_provider
        self.status_manager = status_manager
        self.gpu_lock = gpu_lock
        self.processing_semaphore = processing_semaphore
        self.global_pipeline_lock = global_pipeline_lock

    async def run(
        self, 
        session: SessionContext, 
        state: MeetingState, 
        context: Optional[str] = None,
        trace: Any = None
    ) -> MeetingState:
        """Основной цикл рассуждений и выполнения инструментов агента."""
        file_id = state.file_id

        def update_state(status: str, msg: str):
            state.status = status
            state.progress_message = msg
            state.updated_at = datetime.now(timezone.utc).isoformat()
            self.status_manager.update(file_id, state.to_persistence_dict())

        async with self.global_pipeline_lock:
            try:
                # ----------------------------------------------------
                # Шаг 1: Нормализация входного файла (Tool: normalize_file)
                # ----------------------------------------------------
                update_state("starting", "Нормализация входного файла...")
                norm_res = await execute_tool_call(
                    "normalize_file",
                    {"file_path": state.local_path, "file_id": file_id},
                    session_id=session.session_id,
                    state=state,
                    trace=trace
                )
                norm_data = norm_res["data"]
                state.media_type = norm_data.get("type")
                state.normalized_path = norm_data.get("path")

                # ----------------------------------------------------
                # Шаг 2: Транскрибация речи (Tool: transcribe_audio)
                # ----------------------------------------------------
                async with self.gpu_lock:
                    async with self.processing_semaphore:
                        if state.media_type == "text":
                            state.raw_transcription = norm_data.get("content")
                        else:
                            update_state("transcribing", "Распознавание речи (STT)...")
                            stt_res = await execute_tool_call(
                                "transcribe_audio",
                                {
                                    "audio_path": state.normalized_path, 
                                    "file_id": file_id,
                                    "initial_prompt": context
                                },
                                session_id=session.session_id,
                                state=state,
                                ai_provider=self.ai_provider,
                                status_updater=lambda s, m: update_state(s, m),
                                trace=trace
                            )
                            state.raw_transcription = stt_res["data"]["transcription"]

                        # ----------------------------------------------------
                        # Шаг 3: Улучшение расшифровки (Tool: refine_transcript)
                        # ----------------------------------------------------
                        current_transcript = state.raw_transcription
                        if context:
                            update_state("transcribing", "Интеллектуальная коррекция терминов (AI)...")
                            refine_res = await execute_tool_call(
                                "refine_transcript",
                                {"transcription": current_transcript, "context": context},
                                session_id=session.session_id,
                                state=state,
                                ai_provider=self.ai_provider,
                                trace=trace
                            )
                            state.refined_transcription = refine_res["data"]["refined_transcription"]
                            current_transcript = state.refined_transcription

                        # ----------------------------------------------------
                        # Шаг 4: Генерация протокола (Tool: generate_protocol)
                        # ----------------------------------------------------
                        update_state("generating", "Формирование протокола совещания...")
                        proto_res = await execute_tool_call(
                            "generate_protocol",
                            {
                                "transcription": current_transcript,
                                "context": context,
                                "file_id": file_id
                            },
                            session_id=session.session_id,
                            state=state,
                            ai_provider=self.ai_provider,
                            status_updater=lambda s, m: update_state(s, m),
                            trace=trace
                        )
                        state.protocol_markdown = proto_res["data"].get("text", "")

                        # ----------------------------------------------------
                        # Шаг 5: Аудит протокола (Tool: verify_protocol)
                        # ----------------------------------------------------
                        update_state("verifying", "Аудит протокола и проверка галлюцинаций...")
                        audit_res = await execute_tool_call(
                            "verify_protocol",
                            {
                                "transcription": current_transcript,
                                "protocol": state.protocol_markdown or "",
                                "context": context
                            },
                            session_id=session.session_id,
                            state=state,
                            ai_provider=self.ai_provider,
                            trace=trace
                        )
                        audit_data = audit_res["data"]
                        state.verification_report = audit_data.get("verification_report", "")
                        state.scores = audit_data.get("scores", {})

                # Освобождение GPU

                # ----------------------------------------------------
                # Шаг 6: Генерация DOCX файла (Tool: generate_docx)
                # ----------------------------------------------------
                update_state("generating", "Создание официального DOCX документа...")
                docx_res = await execute_tool_call(
                    "generate_docx",
                    {"protocol_text": state.protocol_markdown or ""},
                    session_id=session.session_id,
                    state=state,
                    trace=trace
                )
                state.docx_path = docx_res["data"]["docx_path"]

                # ----------------------------------------------------
                # Шаг 7: Отправка Email (Tool: send_email + Approval Gate)
                # ----------------------------------------------------
                if state.should_send_email and state.recipient_email:
                    # Попытка вызова инструмента через Approval Gate
                    email_call_res = await execute_tool_call(
                        "send_email",
                        {
                            "recipient": state.recipient_email,
                            "subject": f"Протокол: {state.filename}",
                            "body": "Ваш протокол готов.",
                            "attachment_path": state.docx_path,
                            "confirmed": state.email_approved
                        },
                        session_id=session.session_id,
                        state=state,
                        trace=trace
                    )

                    if email_call_res.get("status") == "blocked" and email_call_res.get("approval_required"):
                        # Переход в состояние ожидания подтверждения оператором
                        update_state(
                            "waiting_for_approval", 
                            "Протокол сформирован. Ожидается подтверждение отправки на почту."
                        )
                        return state
                    else:
                        state.email_sent = True

                update_state("completed", "Обработка успешно завершена.")
                
                # Cleanup temporary media files
                for p in [state.local_path, state.normalized_path]:
                    try:
                        if p and os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass

                return state

            except Exception as e:
                logger.exception(f"Critical error in ADKAgentRunner for {file_id}: {e}")
                update_state("error", str(e))
                raise e

    async def approve_and_dispatch_email(
        self, 
        session: SessionContext, 
        state: MeetingState, 
        trace: Any = None
    ) -> Dict[str, Any]:
        """Возобновление выполнения после получения одобрения оператора."""
        state.email_approved = True
        self.status_manager.update(state.file_id, state.to_persistence_dict())

        email_call_res = await execute_tool_call(
            "send_email",
            {
                "recipient": state.recipient_email,
                "subject": f"Протокол: {state.filename}",
                "body": "Ваш протокол готов.",
                "attachment_path": state.docx_path,
                "confirmed": True
            },
            session_id=session.session_id,
            state=state,
            trace=trace
        )
        
        state.email_sent = True
        state.status = "completed"
        state.progress_message = "Протокол успешно отправлен на почту."
        self.status_manager.update(state.file_id, state.to_persistence_dict())
        return email_call_res
