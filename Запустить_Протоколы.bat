@echo off
setlocal
chcp 65001 >nul

echo ==========================================
echo [!] Запуск системы "Протоколист" (Windows Native)
echo ==========================================

:: 1. Очистка портов
echo [1/3] Проверка портов...
taskkill /F /IM python* /T 2>nul
taskkill /F /IM node* /T 2>nul

:: 2. Проверка зависимостей (быстрая)
if not exist "backend\venv" (
    if not exist "backend\requirements.txt" (
        echo [ERROR] Папка backend не найдена!
        pause
        exit /b
    )
)

:: 3. Запуск сервисов
echo [2/3] Запуск Бэкенда...
start "Backend" cmd /k "cd backend && python main.py"

echo [3/3] Запуск Фронтенда...
start "Frontend" cmd /k "cd frontend && npm run dev"

timeout /t 5 >nul

echo.
echo ==========================================
echo [+] СИСТЕМА УСПЕШНО ЗАПУЩЕНА!
echo.
echo [!] Фронтенд (Интерфейс): http://localhost:5177
echo [!] Бэкенд (API):         http://localhost:8000
echo.
echo [!] ПРИМЕЧАНИЕ: Если это первый запуск,
echo     модели ИИ могут загружаться 2-5 минут.
echo ==========================================
echo.
start http://localhost:5177
pause
