# Meeting Protocol Creator 📝🎤

Автоматизированная система создания профессиональных протоколов совещаний из аудиозаписей с использованием ИИ.

---

## 🛠 Технологический стек проекта

| Компонент | Технологии |
|-----------|------------|
| **Frontend** | React, Vite, CSS (Modern UI/UX), Axios |
| **Backend** | Python, FastAPI, Uvicorn |
| **AI / ML** | Yandex SpeechKit (STT), Yandex GPT (LLM) |
| **Инструменты** | FFmpeg (конвертация аудио), Python-docx (генерация Word) |
| **Email** | SMTP Integration |

---

## 📊 Архитектура и Процесс (Mermaid)

```mermaid
graph TD
    User[👤 Пользователь] -->|Browser| Proxy[🌐 Nginx Proxy (Port 90)]
    Proxy -->|Static Assets| Frontend[⚛️ Frontend: React]
    Proxy -->|API Proxy /api| Backend[🐍 Backend: FastAPI]
    
    subgraph "Backend Layer (Docker)"
        Backend -->|MIME Validation| Magic[🛡️ Magic Check]
        Backend -->|Normalization| FFmpeg[🎵 FFmpeg]
        FFmpeg -->|Speech-to-Text| SpeechKit[☁️ Yandex SpeechKit]
        SpeechKit -->|LLM Optimization| GPT[🤖 Yandex GPT]
        GPT -->|Document Generation| Docx[📄 Python-docx]
    end
    
    Docx -->|SMTP| Email[📧 Email Service]
    Docx -->|Storage| Disk[💾 /temp_protocols]
    
    Email --> Done[🏁 Готовый протокол]
    Disk --> Done
```

---

## ⭐ Сложность проекта
**Сложность: ⭐⭐⭐⭐ (4 звезды - Middle+/Senior)**

*Интеграция нескольких облачных API, сложная обработка аудио потоков через FFmpeg, и динамическая генерация документов со строгим корпоративным форматированием делают этот проект серьезным инженерным решением.*

---

## 🚀 Как запустить (Docker - Рекомендуется)

Самый простой и надежный способ запустить проект — использовать Docker Compose.

1.  **Настройка окружения:** Убедитесь, что в папке `backend/.env` прописаны ваши ключи (Yandex Cloud API Key, Folder ID и др.).
2.  **Запуск:** В корне проекта выполните команду:
    ```bash
    docker-compose up -d --build
    ```
3.  **Доступ:**
    *   **Frontend:** [http://localhost:90](http://localhost:90) 🌐
    *   **Backend API:** [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI) 📑
    *   **Health Check:** [http://localhost:8000/health](http://localhost:8000/health) 🩺

### Ручной запуск (Dev)

Если вы хотите запустить проект без Docker:
1.  **Бэкенд:** `cd backend`, `pip install -r requirements.txt`, `python -m uvicorn main:app --port 8000`
2.  **Фронтенд:** `cd frontend`, `npm install`, `npm run dev -- --port 90` (предварительно поменяв API URL в `api.js`)

---

## ✨ Основные возможности
- **Мировые стандарты:** Протоколы оформляются по правилам международного делового оборота.
- **Умные таблицы:** Поручения автоматически извлекаются из текста и упаковываются в Word-таблицу.
- **Поддержка тяжелых файлов:** Автоматическая конвертация и сжатие аудио для стабильной работы API.
