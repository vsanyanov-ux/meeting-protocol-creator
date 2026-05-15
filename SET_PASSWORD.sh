#!/bin/bash

# Protocolist: Set Admin Password (Linux version)

echo "======================================================"
echo "  PROTOCOLIST: Установка пароля администратора"
echo "======================================================"
echo ""

# Check if python is installed
if command -v python3 &> /dev/null; then
    python3 backend/scripts/hash_password.py
elif command -v python &> /dev/null; then
    python backend/scripts/hash_password.py
else
    echo "[ERROR] Python is not installed on this system."
    echo "Please install python3 to run the password hashing script."
fi

echo ""
read -p "Press enter to exit..."
