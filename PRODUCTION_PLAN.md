# 🗺️ Production Plan: Meeting Protocol Creator

> Задачи упорядочены: быстрые победы сначала, архитектура — потом.
> Каждую задачу применяем отдельно → коммитим → тестируем вручную → идём дальше.

---

## Статус задач

| # | Задача | Время | Статус |
|---|--------|-------|--------|
| 1 | 🔒 Быстрые security-фиксы | ~30 мин | ✅ DONE |
| 2 | ⬇️ Endpoint скачивания DOCX | ~45 мин | ✅ DONE |
| 3 | 🎞️ Мультиформатность (normalizer) | ~2-3 ч | ✅ DONE |
| 4 | 🏗️ Provider Pattern рефакторинг | ~3-4 ч | ✅ DONE |
| 5 | ⏱️ Надёжность (таймауты + очистка) | ~1-2 ч | ✅ DONE |
| 6 | 📋 Логирование | ~1 ч | ✅ DONE |
| 7 | 🚦 Очередь и лимиты | ~2 ч | ✅ DONE |
| 8 | 🧪 Тесты | ~4-6 ч | ✅ DONE |
| 9 | 🐳 Docker | ~2 ч | ✅ DONE |
| 10 | 📦 Зависимости с версиями | ~30 мин | ⬜ TODO |

---

## Задача 1 — 🔒 Быстрые security-фиксы
**Файл:** `backend/main.py`
**Время:** ~30 мин

### Что делаем:
- [ ] Заменить `allow_origins=["*"]` на конкретные origins
- [ ] Добавить middleware с лимитом размера файла (500 МБ)
- [ ] Добавить валидацию env-переменных при старте

### Acceptance criteria:
- Запрос с неизвестного origin блокируется
- Файл >500 МБ получает ответ 413
- Приложение не стартует без `YANDEX_API_KEY` и `YANDEX_FOLDER_ID`

---

## Задача 2 — ⬇️ Endpoint скачивания DOCX
**Файлы:** `backend/main.py`, `frontend/src/App.jsx`, `frontend/src/api.js`
**Время:** ~45 мин

### Что делаем:
- [ ] Добавить `GET /download/{file_id}` в backend
- [ ] Сохранять `docx_path` в `processing_status[file_id]`
- [ ] Добавить кнопку "Скачать протокол" во frontend
- [ ] В `api.js` добавить `downloadProtocol(fileId)`

### Acceptance criteria:
- После завершения есть кнопка скачивания
- Кнопка скачивает реальный `.docx` файл
- Работает даже без настроенного SMTP

---

## Задача 3 — 🎞️ Мультиформатность (normalizer)
**Новый файл:** `backend/normalizer.py`
**Изменить:** `backend/main.py`
**Время:** ~2-3 ч

### Что делаем:
- [ ] Создать `backend/normalizer.py`:
  - `validate_file(file_path)` — проверка по MIME, не расширению
  - `normalize_to_audio(file_path, output_path)` — всё в OGG Opus
  - `extract_text_from_file(file_path)` — для TXT/PDF/DOCX
- [ ] Расширить поддерживаемые форматы в `main.py`:
  - Видео: `mp4, webm, mkv, mov, avi`
  - Аудио доп: `ogg, opus, wma, flac`
  - Текст: `txt, pdf, docx`

### Зависимости:
```bash
pip install python-magic pdfplumber
```

### Acceptance criteria:
- MP4 (Zoom) и WEBM (Google Meet) обрабатываются
- TXT/PDF пропускают этап STT — идут сразу в LLM
- Переименованный PDF в .mp3 отклоняется с понятной ошибкой

---

## Задача 4 — 🏗️ Provider Pattern рефакторинг
**Новая папка:** `backend/providers/`
**Изменить:** `backend/main.py`
**Время:** ~3-4 ч

### Что делаем:
- [ ] `backend/providers/__init__.py`
- [ ] `backend/providers/base.py` — абстрактный `BaseAIProvider`
- [ ] `backend/providers/yandex_provider.py` — текущий `YandexClient` сюда
- [ ] `backend/providers/local_provider.py` — Whisper + Ollama
- [ ] `backend/providers/sber_provider.py` — SaluteSpeech + GigaChat
- [ ] Фабрика `get_provider()` в `main.py`

### Новые env переменные:
```env
AI_PROVIDER=yandex   # yandex | local | sber

# local:
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
WHISPER_MODEL=medium

# sber:
SBER_CLIENT_ID=...
SBER_CLIENT_SECRET=...
```

### Acceptance criteria:
- `AI_PROVIDER=yandex` — работает как раньше
- `AI_PROVIDER=local` — работает без интернета
- `AI_PROVIDER=sber` — работает через GigaChat + SaluteSpeech
- Переключение = одна строка в `.env`

---

## Задача 5 — ⏱️ Надёжность (таймауты + очистка)
**Файлы:** `backend/yandex_client.py`, `backend/main.py`
**Время:** ~1-2 ч

### Что делаем:
- [ ] Убрать `while True:` → таймаут 10 мин в `transcribe_long`
- [ ] Добавить `timeout=300` в `subprocess.run` для ffmpeg
- [ ] Исправить `finally` — удалять все файлы (аудио + DOCX + чанки)
- [ ] Разделить статусы: `completed` / `completed_no_email` / `error`

### Acceptance criteria:
- Зависший Yandex API → ошибка через 10 мин, не вечное ожидание
- После обработки — все временные файлы удалены
- Провал email ≠ провал всей задачи

---

## Задача 6 — 📋 Логирование
**Файлы:** все `backend/*.py`
**Время:** ~1 ч

### Что делаем:
- [ ] Создать `backend/logger.py` с настройкой логгера
- [ ] Заменить все `print()` на `logger.info/error/warning`
- [ ] Запись в `app.log` с ротацией (7 дней, 10 МБ)
- [ ] Логировать: этап, file_id, время выполнения

### Acceptance criteria:
- `app.log` создаётся при запуске
- Каждый этап пишет INFO с file_id и временем
- Ошибки пишут ERROR с traceback

---

## Задача 7 — 🚦 Очередь и лимиты
**Файл:** `backend/main.py`
**Время:** ~2 ч

### Что делаем:
- [ ] `asyncio.Semaphore(3)` — максимум 3 параллельных задачи
- [ ] Показывать позицию в очереди в статусе
- [ ] Фоновая задача: очистка файлов старше 24 ч (каждый час)
- [ ] `GET /health` — статус, очередь, занятый диск

### Acceptance criteria:
- 5 одновременных загрузок → 3 обрабатываются, 2 ждут
- Файлы старше 24 ч удаляются автоматически
- `/health` возвращает `{"status":"ok","queue":2,"disk_mb":145}`

---

## Задача 8 — 🧪 Тесты
**Новая папка:** `backend/tests/`
**Время:** ~4-6 ч

### Файлы:
- [ ] `tests/conftest.py` — фикстуры и моки провайдеров
- [ ] `tests/test_api.py` — 6+ тестов HTTP
- [ ] `tests/test_providers.py` — 6+ тестов провайдеров (через моки)
- [ ] `tests/test_normalizer.py` — 5+ тестов форматов
- [ ] `tests/test_protocol_gen.py` — 8+ тестов DOCX
- [ ] `tests/test_email_client.py` — 3+ теста

### Запуск:
```bash
pip install pytest pytest-asyncio httpx pytest-mock pytest-cov
pytest tests/ -v --cov=. --cov-report=html
```

### Acceptance criteria:
- Все тесты без реальных API-запросов (моки)
- Покрытие > 70%
- Выполняются за < 30 секунд

---

## Задача 9 — 🐳 Docker
**Новые файлы:** `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`
**Время:** ~2 ч

### Что делаем:
- [ ] `backend/Dockerfile` с ffmpeg
- [ ] `frontend/Dockerfile` с nginx
- [ ] `docker-compose.yml`
- [ ] `.dockerignore` для обоих сервисов

### Acceptance criteria:
- `docker-compose up --build` запускает всё с нуля
- Frontend на `http://localhost`, backend на `:8000`
- Работает на чистой машине без Python/Node

---

## Задача 10 — 📦 Зафиксировать версии зависимостей
**Файл:** `backend/requirements.txt` + `backend/requirements-dev.txt`
**Время:** ~30 мин

### Что делаем:
- [ ] Зафиксировать версии всех пакетов
- [ ] Разделить на `requirements.txt` (prod) и `requirements-dev.txt` (тесты)

### Acceptance criteria:
- `pip install -r requirements.txt` — без ошибок на чистом Python
- Версии зафиксированы (не `fastapi`, а `fastapi==0.115.0`)

---

## Порядок коммитов

```
feat: task-1 security fixes (CORS, size limit, env validation)
feat: task-2 add /download/{file_id} endpoint + frontend button
feat: task-3 multi-format support with normalizer module
refactor: task-4 provider pattern (yandex / local / sber)
fix: task-5 reliability (polling timeout, file cleanup)
feat: task-6 structured logging to file with rotation
feat: task-7 queue semaphore, /health endpoint, auto-cleanup
test: task-8 full test suite 70%+ coverage
feat: task-9 docker setup (backend + frontend)
chore: task-10 pin all dependency versions
```
