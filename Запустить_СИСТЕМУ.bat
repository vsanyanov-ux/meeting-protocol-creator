@echo off
setlocal
:: Ensure we are in the script directory
cd /d "%~dp0"

echo ==========================================
echo [!] STARTING PROTOCOLIST (NATIVE WIN)
echo ==========================================

:: 1. Force kill existing processes to free ports
echo [1/3] Cleaning up processes...
taskkill /F /IM python* /T 2>nul
taskkill /F /IM node* /T 2>nul
timeout /t 2 >nul

:: 2. Start Backend
echo [2/3] Starting Backend...
cd backend
start "Backend" python main.py
if %errorlevel% neq 0 (
    echo Error starting Backend!
    pause
    exit /b
)
cd ..

:: 3. Start Frontend
echo [3/3] Starting Frontend...
cd frontend
start "Frontend" npm run dev
if %errorlevel% neq 0 (
    echo Error starting Frontend!
    pause
    exit /b
)
cd ..

echo.
echo ==========================================
echo [+] SYSTEM IS LAUNCHING
echo [!] Please wait a few seconds for UI to load.
echo [!] Backend: http://localhost:8000
echo [!] Frontend: http://localhost:5177
echo ==========================================
echo.

:: Open browser after a small delay
timeout /t 5 >nul
start http://localhost:5177

echo Done. You can minimize this window but DO NOT CLOSE IT.
pause
