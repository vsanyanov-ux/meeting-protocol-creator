@echo off
echo [Switching to Yandex Cloud AI...]
powershell -Command "(gc backend/.env) -replace 'AI_PROVIDER=local', 'AI_PROVIDER=yandex' | Out-File -encoding utf8 backend/.env"
docker compose up -d backend
echo [DONE] Now using Yandex GPT.
pause
