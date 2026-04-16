@echo off
SETLOCAL EnableDelayedExpansion

echo ===================================================
echo   Протоколист: Запуск автоматизированных тестов
echo ===================================================

:: Check for environment
if not exist venv (
    echo [!] Виртуальное окружение не найдено. Попробуйте запустить install.bat первым.
    :: Continue anyway if python is in path
)

echo [1/3] Запуск Unit и интеграционных тестов провайдеров...
pytest backend/tests/test_providers.py backend/tests/test_normalizer.py -v

echo.
echo [2/3] Запуск E2E тестов пайплайна (с моками AI)...
pytest backend/tests/test_e2e_pipeline.py backend/tests/test_api_endpoints.py -v

echo.
echo [3/3] Запуск тестов реального STT (Whisper tiny)...
echo (Этот шаг будет пропущен, если WHISPER_TEST=true не установлена)
SET WHISPER_TEST=true
pytest backend/tests/test_providers.py::test_whisper_local_stt -v

echo.
echo ===================================================
echo   Тестирование завершено!
echo ===================================================
pause
