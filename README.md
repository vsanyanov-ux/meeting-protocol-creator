# Протоколист v5.0.0 🚀📝🎥🎤

Автоматизированная система создания профессиональных протоколов совещаний из видео и аудиозаписей с использованием ИИ. 
**Версия 5.0.0 (High-Speed Turbo & VRAM Optimization)**

---

## 📊 Архитектура и Процесс

```mermaid
graph TD
    User["👤 Пользователь"] -->|Browser| Proxy["🌐 Nginx Proxy (Port 90)"]
    Proxy -->|Static Assets| Frontend["⚛️ Frontend: React"]
    Proxy -->|"API Proxy /api"| Backend["🐍 Backend: FastAPI"]
    
    subgraph "Backend Layer (Docker)"
        Backend -->|Normalization| FFmpeg["🎵 FFmpeg"]
        
        FFmpeg --> AI_Router{"🤖 AI Provider Router"}
        
        AI_Router -->|Local| Local_AI[/"🏠 Local AI: Ollama + Whisper"/]
        AI_Router -->|Cloud| Cloud_AI[/"☁️ Cloud AI: Yandex SpeechKit/GPT"/]
        
        Local_AI -->|Hardware Failure| Fallback_CPU[/"🐢 CPU Fallback"/]
        Fallback_CPU -->|Resource Error| Cloud_AI
        
        Local_AI --> Docx["📄 Document Generation (Word)"]
        Cloud_AI --> Docx
        Fallback_CPU --> Docx
    end
    
    Docx -->|SMTP| Email["📧 Email Service"]
    Docx -->|Storage| Disk["💾 /temp_protocols"]
    
    Email --> Done["🏁 Готовый протокол"]
    Disk --> Done
```

---

## ✨ Ключевые особенности v5.0.0
- **🚀 Whisper Large-v3-Turbo:** Ускорение транскрипции до 3 раз по сравнению со стандартными моделями при сопоставимой точности.
- **🛡️ VRAM Hot-Swap:** Динамическое управление видеопамятью через `keep_alive: 0`. Полная поддержка карт RTX 3060 12GB даже для длинных записей (1ч+).
- **🎙️ Hybrid Diarization:** Двухэтапное распознавание спикеров (аудио-анализ + семантическая привязка имен в LLM).
- **🛡️ Resilience (Отказоустойчивость):** Внедрена система **Atomic Persistence** на базе SQLite для надежного возобновления работы.
- **🧠 Langfuse Observability:** Глубокий мониторинг качества и стоимости каждой встречи через Langfuse SDK.
- **🚀 Multi-worker Backend:** Поддержка нескольких воркеров обеспечивает мгновенную реакцию интерфейса.
- **🔒 Hardware Coordination:** Защита от конфликтов ресурсов через `gpu.lock`.

---

## 🛠 Технологический стек

| Компонент | Технологии |
|-----------|------------|
| **Frontend** | React, Vite, Framer Motion, Glassmorphism UI |
| **Backend** | Python, FastAPI, Pydantic |
| **Local AI** | Ollama (Qwen 2.5 7B), Faster-Whisper (CUDA Optimized) |
| **Cloud AI** | Yandex SpeechKit v2, Yandex GPT (Latest) |
| **Observability** | Langfuse v4 (SDK + UI) |
| **Tracing** | OpenTelemetry compatible status tracking |

---

## ⭐ Сложность проекта
**Сложность: ⭐⭐⭐⭐⭐ (5 звезд - Senior / Enterprise)**

*Проект представляет собой отказоустойчивый конвейер данных, способный работать в изолированных контурах (Local Only) или гибридных облаках с автоматическим управлением ресурсами.*

---

## 🚀 Быстрый старт (Docker)

1.  **Настройка:** Отредактируйте `backend/.env`. 
    - Установите `AI_PROVIDER=local` для работы на своем ПК.
    - Установите `AI_PROVIDER=yandex` для использования облачных мощностей.
2.  **Запуск (GPU NVIDIA - Рекомендуется):**
    ```bash
    docker-compose up -d --build
    ```
3.  **Запуск (CPU Fallback):**
    Система автоматически переключится на CPU, если GPU не будет обнаружен, но вы можете принудительно отключить reservations в `docker-compose.yml`.

---

## 💻 Системные требования
- **GPU**: NVIDIA RTX 3060 12GB+ (для Turbo-режима).
- **RAM**: Минимум 16 ГБ RAM (8 ГБ для WSL2).
- **OS**: Windows (с NVIDIA Container Toolkit) или Linux.

---

## ✨ Основные возможности
- **Мировые стандарты:** Протоколы по ГОСТ и правилам международного делового оборота.
- **Умные таблицы:** Автоматическая упаковка поручений в DOCX-таблицы.
- **Интеграция с Email:** Рассылка результатов участникам "в один клик".
- **Безопасность**: Полная приватность данных в режиме Local.
