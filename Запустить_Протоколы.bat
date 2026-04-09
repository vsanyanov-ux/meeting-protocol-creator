@echo off
setlocal

echo [!] Checking environment...

:: Detect docker command (modern 'docker compose' vs old 'docker-compose')
docker compose version >nul 2>&1
if %errorlevel% equ 0 (
    set D_CMD=docker compose
) else (
    set D_CMD=docker-compose
)

echo [+] Using: %D_CMD%

echo [+] Cleaning up old containers...
%D_CMD% down >nul 2>&1

:: Check for NVIDIA GPU
nvidia-smi >nul 2>&1
if %errorlevel% equ 0 (
    echo [+] NVIDIA GPU found. Starting with GPU support...
    %D_CMD% -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
) else (
    echo [!] No NVIDIA GPU found, using CPU.
    %D_CMD% up -d --build
)

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start containers!
    pause
    exit /b
)

echo.
echo ==========================================
echo [+] SYSTEM STARTED SUCCESSFULLY!
echo.
echo [!] Frontend: http://localhost:90
echo [!] Backend:  http://localhost:8000
echo.
echo [!] NOTE: First protocol generation will 
echo     download the model (2GB). 
echo     Please wait 2-5 minutes.
echo ==========================================
echo.
pause
