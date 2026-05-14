import hashlib
import sys
import os

def generate_hash():
    print("\n--- Protocolist Password Hasher ---")
    password = input("Введите пароль для защиты приложения: ").strip()
    
    if not password:
        print("Ошибка: Пароль не может быть пустым.")
        return

    # Generate SHA-256 hash
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    
    print("\n" + "="*40)
    print("ВАШ ХЭШ ДЛЯ ФАЙЛА .env:")
    print(f"APP_PASSWORD_HASH={pwd_hash}")
    print("="*40)
    print("\nИнструкция:")
    print("1. Откройте файл .env в папке backend.")
    print("2. Добавьте или замените строку выше.")
    print("3. Удалите старую строку APP_PASSWORD (если она есть).")
    print("4. Перезапустите контейнеры: docker-compose up -d")
    print("="*40 + "\n")

if __name__ == "__main__":
    generate_hash()
