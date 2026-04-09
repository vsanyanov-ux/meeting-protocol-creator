# Meeting Protocol Creator 📝🎤

Автоматизированная система создания профессиональных протоколов совещаний из аудиозаписей с использованием ИИ.

---

## 🚀 Что нового в Версии 2.0
- **Локальный ИИ (Offline Mode)**: Полная независимость от облаков с использованием **Ollama** и **Faster-Whisper**.
- **Умные таблицы**: Поручения и принятые решения теперь строго структурируются в виде Markdown-таблиц.
- **Оптимизация ресурсов**: Настроено под модели **Qwen 2.5 (3B)** и **Whisper Medium/Small** для работы на стандартных ноутбуках (16GB RAM).
- **GPU Acceleration**: Поддержка ускорения вычислений на видеокартах NVIDIA.
- **AI-Аудитор**: Система двойной проверки (self-critique) для исключения галлюцинаций ИИ.

---

## 📊 Архитектура и Процесс (v2.0)

`mermaid
graph TD
    User["👤 Пользователь"] -->|Browser| Proxy["🌐 Nginx Proxy (Port 90)"]
    Proxy -->|Static Assets| Frontend["⚛️ Frontend: React"]
    Proxy -->|"API Proxy /api"| Backend["🐍 Backend: FastAPI"]
    
    subgraph "Backend Layer (Docker)"
        Backend -->|"MIME Validation"| Magic["🛡️ Magic Check"]
        Backend -->|Normalization| FFmpeg["🎵 FFmpeg"]
        
        FFmpeg --> AI_Router{"🤖 AI Provider Router"}
        
        AI_Router -->|Local| Local_AI[/"🏠 Local AI: Ollama + Whisper"/]
        AI_Router -->|Cloud| Cloud_AI[/"☁️ Cloud AI: Yandex SpeechKit/GPT"/]
        
        Local_AI --> Docx["📄 Document Generation (Word)"]
        Cloud_AI --> Docx
    end
    
    Docx -->|SMTP| Email["📧 Email Service"]
    Docx -->|Storage| Disk["💾 /temp_protocols"]
    
    Email --> Done["🏁 Готовый протокол"]
    Disk --> Done
`

---

## 🛠 Технологический стек

| Компонент | Технологии |
|-----------|------------|
| **Frontend** | React, Vite, Framer Motion, Glassmorphism UI |
| **Backend** | Python, FastAPI, Pydantic |
| **Local ML** | Ollama (LLM), Faster-Whisper (STT - int8) |
| **Cloud ML** | Yandex SpeechKit, Yandex GPT (Latest) |
| **Core Tools** | FFmpeg, Magic-Python, Python-docx |

---

## ⭐ Сложность проекта
**Сложность: ⭐⭐⭐⭐ (4 звезды - Middle+/Senior)**

*Проект сочетает в себе сложный аудио-процессинг, гибридную архитектуру нейросетей и динамическую генерацию корпоративной отчетности. Это не просто оболочка над GPT, а полноценный конвейер обработки данных.*

---

## 🚀 Быстрый старт (Docker)

1.  **Настройка:** Отредактируйте ackend/.env. 
    - Установите AI_PROVIDER=local для работы на своем ПК.
    - Установите AI_PROVIDER=yandex для использования облачных мощностей.
2.  **Запуск (CPU - по умолчанию):**
    `ash
    docker-compose up -d --build
    `
3.  **Запуск (GPU - NVIDIA):**
    `ash
    docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
    `

---

## 🎙️ Профессиональная диаризация
В системе реализованы два режима разделения спикеров:
1.  **AI-Fallback:** Анализ текста и контекста для разделения реплик силами LLM.
2.  **Cloud Diarization:** Точное распознавание голосов через Yandex SpeechKit (требует настройки S3-бакета).

---

## ✨ Основные возможности
- **Мировые стандарты:** Протоколы оформляются по правилам международного делового оборота.
- **Умные таблицы:** Поручения автоматически упаковываются в Word/Markdown таблицы.
- **Интеграция с Email:** Автоматическая рассылка протоколов участникам.
- **Безопасность**: Полностью приватный режим при использовании локальных моделей.