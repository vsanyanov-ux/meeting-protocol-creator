# 🎙️ Meeting Protocol Creator («Протоколист»)

[![Google ADK Standard](https://img.shields.io/badge/Google%20ADK-Compliant-brightgreen.svg)](https://github.com/google/agents-cli)
[![AEBOP Certified](https://img.shields.io/badge/AEBOP™-Standardized-blue.svg)](https://github.com/vsanyanov-ux/meeting-protocol-creator)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-009688.svg)](https://fastapi.tiangolo.com)
[![Langfuse v4](https://img.shields.io/badge/Langfuse-v4.0.6-orange.svg)](https://langfuse.com)
[![Quality Flywheel](https://img.shields.io/badge/Quality%20Flywheel-99.6%25-green.svg)](tests/eval/)

**Meeting Protocol Creator** — корпоративная агентная система для автоматической генерации, аудита и экспорта протоколов совещаний из аудио-, видео- и текстовых записей. 

Архитектура системы полностью модернизирована по промышленному стандарту **Google Agent Development Kit (ADK)** и принципам **AEBOP™ (Agentic Engineering Body of Practices)**.

---

## 🌟 Ключевые возможности

- 🤖 **ADK Agent Runtime**: Агентный исполнитель `ADKAgentRunner` с когнитивным циклом оркестрации, адаптивным вызовом инструментов и spin-lock защитой ресурсов GPU.
- 📐 **Standardized Tool Contracts**: Строгая типизация всех операций через **Pydantic**-модели (`BaseModel`, `Field`), централизованный `TOOLS_REGISTRY` и единый диспетчер `execute_tool_call()`.
- 🛡️ **Runtime Governance & Approval Gates**: Централизованные хуки `before_tool_callback` (pre-flight проверки, санитизация от промпт-инъекций) и интерактивный **Approval Gate** для внешних действий (`POST /approve/{file_id}`).
- 🧠 **State & Memory Separation**: Четкое разделение сессионной памяти (`SessionContext`) и структурированного состояния совещания (`MeetingState`: поручения, дедлайны, скоры аудита).
- 📊 **Enterprise Observability**: Полная трассировка всех шагов и вызовов инструментов в **Langfuse v4** по семантическому стандарту OpenInference.
- 🔄 **Quality Flywheel**: Встроенная система непрерывной оценки качества с эталонным датасетом `golden_protocols.json` и порогом качества **≥ 95%** (Faithfulness, Action Items Recall, Hallucination Prevention).
- 📄 **ГОСТ DOCX Экспорт**: Генерация документов Word с официальной типографикой, колонтитулами «КОНФИДЕНЦИАЛЬНО», номерами страниц и структурированными таблицами решений.
- ⚡ **Двойной провайдер AI**:
  - **Local Mode**: Faster-Whisper (CUDA/CPU) + Ollama (`qwen2.5` / `qwen3.5`).
  - **Cloud Mode**: Yandex Cloud (SpeechKit + YandexGPT).

---

## 🏗️ Архитектура системы (ADK Core)

```
backend/
├── core/
│   ├── tools.py            # Pydantic-контракты инструментов, TOOLS_REGISTRY, execute_tool_call()
│   ├── adk_callbacks.py    # Runtime Guardrails, Approval Gates, before/after хуки
│   └── adk_runtime.py      # SessionContext, MeetingState, ADKAgentRunner
├── providers/
│   ├── base.py             # Базовый интерфейс BaseAIProvider
│   ├── local.py            # Локальный провайдер (Whisper + Ollama)
│   └── yandex.py           # Облачный провайдер (Yandex Cloud)
├── tests/
│   ├── eval/               # Quality Flywheel
│   │   ├── eval_config.yaml
│   │   └── datasets/golden_protocols.json
│   └── test_adk_compliance.py # Pytest-сьют соответствия ADK
├── evals/
│   └── run_regression_evals.py # CLI-раннер регрессионных эвалов
├── normalizer.py           # Аудио/видео конвертер (FFmpeg)
├── protocol_generator.py   # Генератор DOCX
├── email_client.py         # Почтовый клиент с поддержкой Approval Gate
└── main.py                 # FastAPI приложение с эндпоинтами ADK
```

---

## 🚀 Запуск приложения

### 1. Локальный запуск на Windows (Native)
1. Убедитесь, что запущен **Ollama** (`ollama serve`).
2. Запустите скрипт запуска:
   ```cmd
   Запустить_СИСТЕМУ.bat
   ```
3. Скрипт автоматически запустит Backend (порт `8000`) и Frontend (порт `5177`).

### 2. Запуск в Docker
```bash
# С поддержкой GPU (NVIDIA Container Toolkit):
docker-compose up -d

# Только на CPU:
docker-compose -f docker-compose.cpu.yml up -d
```
Интерфейс доступен по адресу: `http://localhost:90` или `http://localhost:5177`.

---

## 🧪 Тестирование и Quality Flywheel

### Запуск Unit-тестов и ADK Compliance
```bash
cd backend
python -m pytest tests/ -v
```

### Запуск Quality Flywheel Regression Evals
```bash
cd backend
python evals/run_regression_evals.py --mock --threshold 95
```

---

## 📄 Лицензия
Proprietary Corporate Software. All rights reserved.
