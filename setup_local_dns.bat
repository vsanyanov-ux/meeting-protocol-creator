@echo off
setlocal enabledelayedexpansion

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo [!] ОШИБКА: Этот скрипт нужно запустить ОТ ИМЕНИ АДМИНИСТРАТОРА.
    echo [!] Нажми правой кнопкой на файл и выбери "Запуск от имени администратора".
    echo.
    pause
    exit /b
)

set HOSTS_FILE=%SystemRoot%\System32\drivers\etc\hosts
set NEW_ENTRY=127.0.0.1 protocolist.local

echo.
echo ========================================================
echo [+] Настройка локального адреса: protocolist.local
echo ========================================================

:: Check if entry already exists
findstr /C:"%NEW_ENTRY%" "%HOSTS_FILE%" >nul
if %errorLevel% equ 0 (
    echo [!] Адрес уже настроен в файле hosts.
) else (
    echo [+] Добавляю запись в %HOSTS_FILE%...
    echo. >> "%HOSTS_FILE%"
    echo %NEW_ENTRY% >> "%HOSTS_FILE%"
    echo [+] Готово! Теперь адрес protocolist.local ведет на этот компьютер.
)

echo.
echo [+] Настройка завершена.
echo ========================================================
echo.
pause
