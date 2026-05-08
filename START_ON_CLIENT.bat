@echo off
echo Installing Protocolist (Full Autonomous Mode)...
echo Loading images from USB... Please wait.
docker load -i images/backend.tar
docker load -i images/frontend.tar
docker load -i images/ollama.tar
echo Starting containers...
docker-compose up -d
echo Done! Protocolist is running without internet.
pause