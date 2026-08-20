"""
ADK Runtime Governance, Callbacks & Approval Gates.
Conforms to Google ADK & AEBOP™ (Agentic Engineering Body of Practices).
"""

import os
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from loguru import logger


# ============================================================================
# Security & Guardrail Rules
# ============================================================================

SUSPICIOUS_PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"system\s+override",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"disregard\s+all\s+constraints",
    r"output\s+password(\s+hash)?",
    r"reveal\s+(secret|token|api_key|password)",
    r"<script.*?>",
    r"drop\s+table",
]

def sanitize_user_context(context: Optional[str]) -> Optional[str]:
    """Санитизирует пользовательский контекст от потенциальных промпт-инъекций."""
    if not context:
        return context
    
    cleaned = context.strip()
    for pattern in SUSPICIOUS_PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            logger.warning(f"⚠️ Prompt injection attempt detected and neutralized: {pattern}")
            cleaned = re.sub(pattern, "[FILTERED_UNSAFE_INSTRUCTION]", cleaned, flags=re.IGNORECASE)
    
    return cleaned


def is_valid_email(email_str: str) -> bool:
    """Проверяет валидность email-адреса."""
    if not email_str:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email_str.strip()))


# ============================================================================
# ADK Lifecycle Callbacks
# ============================================================================

async def before_tool_callback(
    tool_name: str, 
    args: Dict[str, Any], 
    session_id: str, 
    state: Any = None
) -> Dict[str, Any]:
    """
    Хук перед выполнением инструмента:
    - Pre-flight валидация
    - Санация входных данных и Guardrails
    - Approval Gate для необратимых действий
    """
    logger.info(f"🛡️ [ADK before_tool_callback] Evaluating tool '{tool_name}' for session '{session_id}'")

    # 1. Approval Gate для необратимых операций (отправка Email)
    if tool_name == "send_email":
        confirmed = args.get("confirmed", False)
        if not confirmed:
            logger.warning(f"🛑 [Approval Gate] Blocked execution of '{tool_name}': operator approval required.")
            return {
                "status": "blocked",
                "approval_required": True,
                "reason": "Требуется явное подтверждение оператора (Approval Gate) перед отправкой письма."
            }
        
        recipient = args.get("recipient", "")
        if not is_valid_email(recipient):
            return {
                "status": "blocked",
                "approval_required": False,
                "reason": f"Некорректный email адрес получателя: '{recipient}'"
            }

    # 2. Guardrails для контекста (санация инъекций)
    if "context" in args and args["context"]:
        args["context"] = sanitize_user_context(args["context"])

    # 3. Pre-flight проверки существования файлов
    if tool_name in ["normalize_file", "transcribe_audio"]:
        file_path = args.get("file_path") or args.get("audio_path")
        if file_path and not os.path.exists(file_path):
            return {
                "status": "blocked",
                "approval_required": False,
                "reason": f"Файл не найден на диске: '{file_path}'"
            }

    return {"status": "allowed", "args": args}


async def after_tool_callback(
    tool_name: str, 
    args: Dict[str, Any], 
    result: Dict[str, Any], 
    session_id: str, 
    state: Any = None,
    trace: Any = None,
    is_error: bool = False
) -> Dict[str, Any]:
    """
    Хук после выполнения инструмента:
    - Стандартизация схемы ответа
    - Генерация спанов OpenInference / OpenTelemetry
    - Аудит действий
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    success = not is_error and ("error" not in result or result.get("error") is None)

    # 1. Запись спана в OpenInference / Langfuse
    if trace and hasattr(trace, "start_span"):
        try:
            span_meta = {
                "openinference.span.kind": "TOOL",
                "tool.name": tool_name,
                "tool.parameters": {k: str(v)[:200] for k, v in args.items() if k != "transcription"},
                "tool.status": "SUCCESS" if success else "ERROR",
                "session.id": session_id
            }
            if hasattr(trace, "log_tool_call"):
                trace.log_tool_call(tool_name, args, result)
        except Exception as e:
            logger.warning(f"Failed to record OpenInference span: {e}")

    logger.info(f"✅ [ADK after_tool_callback] Tool '{tool_name}' completed. Status: {'SUCCESS' if success else 'ERROR'}")

    return {
        "success": success,
        "tool_name": tool_name,
        "data": result,
        "timestamp": timestamp
    }
