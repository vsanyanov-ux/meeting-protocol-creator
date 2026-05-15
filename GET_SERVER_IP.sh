#!/bin/bash

# Meeting Protocol Creator - Network Access Info (Linux version)

echo "=================================================="
echo "  Meeting Protocol Creator - Network Access Info"
echo "=================================================="
echo ""

# Get Local IP
# Works on most Linux distributions
IP=$(hostname -I | awk '{print $1}')

if [ -z "$IP" ]; then
    echo "[ERROR] Could not detect local IP address."
else
    echo "[FOUND] Local IP: $IP"
    echo ""
    echo "--------------------------------------------------"
    echo "  How to access from other computers (Laptop):"
    echo "--------------------------------------------------"
    echo ""
    echo "  1. Interface (Browser): http://$IP:90"
    echo "  2. API Status:          http://$IP:8000/health"
    echo ""
    echo "--------------------------------------------------"
    echo "  IMPORTANT:"
    echo "  Make sure ports 90 and 8000 are open in your "
    echo "  Linux Firewall (ufw or firewalld)."
    echo "--------------------------------------------------"
fi

echo ""
read -p "Press enter to exit..."
