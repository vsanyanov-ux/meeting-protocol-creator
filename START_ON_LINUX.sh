#!/bin/bash

# Protocolist: Start System (Linux version)

echo "=================================================="
echo "  PROTOCOLIST: Starting System (Docker Mode)"
echo "=================================================="

# Check if image archives exist (for offline installation)
if [ -d "images" ]; then
    echo "[1/2] Checking for offline images in /images..."
    
    if [ -f "images/backend.tar" ]; then
        echo "Loading backend.tar..."
        docker load -i images/backend.tar
    fi
    
    if [ -f "images/frontend.tar" ]; then
        echo "Loading frontend.tar..."
        docker load -i images/frontend.tar
    fi
    
    if [ -f "images/ollama.tar" ]; then
        echo "Loading ollama.tar..."
        docker load -i images/ollama.tar
    fi
fi

echo "[2/2] Launching containers..."

# Determine if we should use GPU or CPU
if command -v nvidia-smi &> /dev/null; then
    echo "[INFO] NVIDIA GPU detected. Starting in GPU mode..."
    docker-compose up -d
else
    echo "[WARNING] No NVIDIA GPU detected. Starting in CPU mode..."
    docker-compose -f docker-compose.cpu.yml up -d
fi

echo ""
echo "=================================================="
echo "  [+] SYSTEM IS RUNNING"
echo "  Backend: http://localhost:8000"
echo "  Frontend: http://localhost:90"
echo "=================================================="
echo ""

# Get IP for remote access
IP=$(hostname -I | awk '{print $1}')
echo "Remote access via: http://$IP:90"
echo ""

read -p "Press enter to exit..."
