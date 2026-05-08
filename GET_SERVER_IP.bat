@echo off
setlocal enabledelayedexpansion

echo ==================================================
echo   Meeting Protocol Creator - Network Access Info
echo ==================================================
echo.

:: Get Local IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R /C:"IPv4 Address" /C:"IP-адрес IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    echo [FOUND] Local IP: !IP!
)

echo.
echo --------------------------------------------------
echo   How to access from other computers (Laptop):
echo --------------------------------------------------
echo.
echo   1. Interface (Browser): http://!IP!:90
echo   2. API Status:          http://!IP!:8000/health
echo.
echo --------------------------------------------------
echo   IMPORTANT:
echo   Make sure ports 90 and 8000 are open in your 
echo   Windows Firewall for the Private network.
echo --------------------------------------------------
echo.
pause
