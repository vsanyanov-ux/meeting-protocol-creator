"""
Standardized ADK Tool Contracts & Tool Registry.
Conforms to Google ADK and AEBOP™ (Agentic Engineering Body of Practices).
"""

from typing import Dict, Any, Optional, List, Callable, Type
from pydantic import BaseModel, Field
import inspect
import asyncio
from loguru import logger

from normalizer import normalize_file
from protocol_generator import generate_docx
from email_client import send_email


# ============================================================================
# 1. Pydantic Tool Input Schemas
# ============================================================================

class NormalizeFileInput(BaseModel):
    file_path: str = Field(..., description="Абсолютный или относительный путь к входному файлу (аудио, видео, текст)")
    file_id: str = Field(..., description="Уникальный идентификатор задачи")


class TranscribeAudioInput(BaseModel):
    audio_path: str = Field(..., description="Путь к нормализованному аудиофайлу для транскрибации")
    file_id: str = Field(..., description="Уникальный идентификатор задачи")
    initial_prompt: Optional[str] = Field(None, description="Дополнительный контекст/словарь для STT модели")


class RefineTranscriptInput(BaseModel):
    transcription: str = Field(..., description="Сырая текстовая расшифровка аудиозаписи")
    context: Optional[str] = Field(None, description="Контекст совещания (участники, тема, термины) для коррекции ошибок STT")


class GenerateProtocolInput(BaseModel):
    transcription: str = Field(..., description="Текст стенограммы (полный или предварительно очищенный)")
    context: Optional[str] = Field(None, description="Контекст совещания (участники, повестка, термины)")
    file_id: Optional[str] = Field(None, description="Идентификатор задачи для сохранения промежуточных саммари")


class VerifyProtocolInput(BaseModel):
    transcription: str = Field(..., description="Оригинальный текст стенограммы для сверки")
    protocol: Optional[str] = Field("", description="Сгенерированный проект протокола")
    context: Optional[str] = Field(None, description="Дополнительный контекст встречи")


class GenerateDocxInput(BaseModel):
    protocol_text: Optional[str] = Field("", description="Markdown-текст протокола для конвертации в официальный DOCX документ")


class SendEmailInput(BaseModel):
    recipient: str = Field(..., description="Email адрес получателя протокола")
    subject: str = Field(..., description="Тема электронного письма")
    body: str = Field(..., description="Текст сопроводительного сообщения")
    attachment_path: str = Field(..., description="Путь к прикрепляемому DOCX-файлу")
    confirmed: bool = Field(False, description="Флаг явного подтверждения отправки оператором (Approval Gate)")


# ============================================================================
# 2. Tool Wrappers and Implementations
# ============================================================================

async def tool_normalize_file(params: NormalizeFileInput, **kwargs) -> Dict[str, Any]:
    """Нормализует входной медиа-файл или извлекает текст."""
    res = await asyncio.to_thread(normalize_file, params.file_path, params.file_id)
    if res.get("type") == "error":
        raise ValueError(res.get("error", "Ошибка нормализации файла"))
    return res


async def tool_transcribe_audio(params: TranscribeAudioInput, ai_provider: Any = None, status_updater: Optional[Callable] = None, trace: Any = None, **kwargs) -> Dict[str, Any]:
    """Выполняет транскрибацию аудиозаписи в текст через активный AI-провайдер."""
    if not ai_provider:
        raise ValueError("AI Provider is required for transcription")
    
    transcription = await ai_provider.transcribe_audio(
        audio_path=params.audio_path,
        file_id=params.file_id,
        status_updater=status_updater or (lambda s, m: None),
        trace=trace,
        initial_prompt=params.initial_prompt
    )
    if not transcription:
        raise RuntimeError("STT transcription produced empty result")
    return {"transcription": transcription, "length": len(transcription)}


async def tool_refine_transcript(params: RefineTranscriptInput, ai_provider: Any = None, trace: Any = None, **kwargs) -> Dict[str, Any]:
    """Улучшает качество расшифровки и терминологию с учетом контекста."""
    if not ai_provider:
        raise ValueError("AI Provider is required for transcript refinement")
    
    refined = await ai_provider.refine_transcript(
        transcription=params.transcription,
        context=params.context,
        trace=trace
    )
    return {"refined_transcription": refined}


async def tool_generate_protocol(params: GenerateProtocolInput, ai_provider: Any = None, status_updater: Optional[Callable] = None, trace: Any = None, **kwargs) -> Dict[str, Any]:
    """Генерирует структурированный протокол совещания."""
    if not ai_provider:
        raise ValueError("AI Provider is required for protocol generation")
    
    gen_result = await ai_provider.create_protocol(
        transcription=params.transcription,
        status_updater=status_updater or (lambda s, m: None),
        file_id=params.file_id,
        trace=trace,
        context=params.context
    )
    return gen_result


async def tool_verify_protocol(params: VerifyProtocolInput, ai_provider: Any = None, trace: Any = None, **kwargs) -> Dict[str, Any]:
    """Проводит независимый аудит протокола на предмет галлюцинаций и упущенных фактов."""
    if not ai_provider:
        raise ValueError("AI Provider is required for protocol verification")
    
    audit_res = await ai_provider.verify_protocol(
        transcription=params.transcription,
        protocol=params.protocol,
        trace=trace,
        context=params.context
    )
    return audit_res


async def tool_generate_docx(params: GenerateDocxInput, **kwargs) -> Dict[str, Any]:
    """Создает корпоративный DOCX документ по стандартам ГОСТ."""
    docx_path = await asyncio.to_thread(generate_docx, params.protocol_text)
    return {"docx_path": docx_path}


async def tool_send_email(params: SendEmailInput, **kwargs) -> Dict[str, Any]:
    """Отправляет готовый протокол по электронной почте (требует подтверждения Approval Gate)."""
    if not params.confirmed:
        raise PermissionError("Approval required: cannot send email without operator confirmation (confirmed=True)")
    
    success = await asyncio.to_thread(
        send_email,
        params.recipient,
        params.subject,
        params.body,
        params.attachment_path
    )
    return {"sent": bool(success), "recipient": params.recipient}


# ============================================================================
# 3. Centralized Tools Registry
# ============================================================================

TOOLS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "normalize_file": {
        "name": "normalize_file",
        "description": "Извлечение аудиопотока или текста из входного медиафайла",
        "schema": NormalizeFileInput,
        "handler": tool_normalize_file,
        "is_irreversible": False,
    },
    "transcribe_audio": {
        "name": "transcribe_audio",
        "description": "Распознавание речи из аудиофайла (Whisper / SpeechKit)",
        "schema": TranscribeAudioInput,
        "handler": tool_transcribe_audio,
        "is_irreversible": False,
    },
    "refine_transcript": {
        "name": "refine_transcript",
        "description": "Интеллектуальная коррекция терминов и ошибок расшифровки по контексту",
        "schema": RefineTranscriptInput,
        "handler": tool_refine_transcript,
        "is_irreversible": False,
    },
    "generate_protocol": {
        "name": "generate_protocol",
        "description": "Генерация протокола совещания (тезисы, решения, поручения, дедлайны)",
        "schema": GenerateProtocolInput,
        "handler": tool_generate_protocol,
        "is_irreversible": False,
    },
    "verify_protocol": {
        "name": "verify_protocol",
        "description": "Аудит протокола на соответствие стенограмме и выявление галлюцинаций",
        "schema": VerifyProtocolInput,
        "handler": tool_verify_protocol,
        "is_irreversible": False,
    },
    "generate_docx": {
        "name": "generate_docx",
        "description": "Формирование официального DOCX файла со стилизацией ГОСТ",
        "schema": GenerateDocxInput,
        "handler": tool_generate_docx,
        "is_irreversible": False,
    },
    "send_email": {
        "name": "send_email",
        "description": "Отправка DOCX-протокола на email получателя (Approval Gate)",
        "schema": SendEmailInput,
        "handler": tool_send_email,
        "is_irreversible": True,
    },
}


def get_agent_tool_declarations() -> List[Dict[str, Any]]:
    """
    Генерирует стандартизированные JSON-схемы (Google Gemini / OpenAI / ADK)
    для всех зарегистрированных инструментов.
    """
    declarations = []
    for tool_name, tool_info in TOOLS_REGISTRY.items():
        model_cls: Type[BaseModel] = tool_info["schema"]
        schema = model_cls.model_json_schema()
        declarations.append({
            "name": tool_name,
            "description": tool_info["description"],
            "parameters": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", [])
            }
        })
    return declarations


async def execute_tool_call(
    tool_name: str, 
    args: Dict[str, Any], 
    session_id: str, 
    state: Any = None,
    ai_provider: Any = None,
    status_updater: Optional[Callable] = None,
    trace: Any = None
) -> Dict[str, Any]:
    """
    Единый диспетчер выполнения инструментов ADK.
    Выполняет валидацию Pydantic, вызывает before_tool_callback и after_tool_callback.
    """
    if tool_name not in TOOLS_REGISTRY:
        raise KeyError(f"Tool '{tool_name}' is not registered in TOOLS_REGISTRY")
    
    tool_info = TOOLS_REGISTRY[tool_name]
    model_cls: Type[BaseModel] = tool_info["schema"]
    handler = tool_info["handler"]

    # Import callbacks lazily to prevent circular dependencies
    from core.adk_callbacks import before_tool_callback, after_tool_callback

    # 1. Pre-execution Hook (Sanitization, Validation, Approval Gate)
    pre_result = await before_tool_callback(
        tool_name=tool_name, 
        args=args, 
        session_id=session_id, 
        state=state
    )
    
    if pre_result.get("status") == "blocked":
        return {
            "status": "blocked",
            "reason": pre_result.get("reason"),
            "approval_required": pre_result.get("approval_required", False)
        }

    # 2. Pydantic Parsing & Validation
    validated_input = model_cls(**args)

    # 3. Execution
    try:
        raw_result = await handler(
            validated_input,
            ai_provider=ai_provider,
            status_updater=status_updater,
            trace=trace,
            session_id=session_id,
            state=state
        )
        
        # 4. Post-execution Hook (OpenInference tracing, status formatting)
        final_result = await after_tool_callback(
            tool_name=tool_name,
            args=args,
            result=raw_result,
            session_id=session_id,
            state=state,
            trace=trace
        )
        return final_result

    except Exception as exc:
        logger.error(f"Error during tool '{tool_name}' execution: {exc}")
        error_result = await after_tool_callback(
            tool_name=tool_name,
            args=args,
            result={"error": str(exc)},
            session_id=session_id,
            state=state,
            trace=trace,
            is_error=True
        )
        raise exc
