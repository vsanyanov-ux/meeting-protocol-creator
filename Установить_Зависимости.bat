@echo off
setlocal
chcp 65001 >nul

echo ==========================================
echo [+] УСТАНОВКА ЗАВИСИМОСТЕЙ (NATIVE WIN)
echo ==========================================

:: Backend
echo [1/2] Установка Python-библиотек...
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Ошибка при установке Python-зависимостей!
    pause
    exit /b
)
cd ..

:: Frontend
echo [2/2] Установка Node-библиотек (Vite)...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] Ошибка при установке Node-зависимостей!
    pause
    exit /b
)
cd ..

echo.
echo ==========================================
echo [+] Все зависимости успешно установлены!
echo ==========================================
pause
