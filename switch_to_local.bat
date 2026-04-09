@echo off
echo [Switching to Local Offline AI...]
powershell -Command "(gc backend/.env) -replace 'AI_PROVIDER=yandex', 'AI_PROVIDER=local' | Out-File -encoding utf8 backend/.env"
docker compose up -d backend
echo [DONE] Now using Local AI (Ollama/Whisper).
pause
