@echo off
echo === LAPTOP TEST MODE (CPU ONLY) ===
echo.
echo Loading images... 
docker load -i images/backend.tar
docker load -i images/frontend.tar
docker load -i images/ollama.tar
echo.
echo Starting in CPU mode...
docker-compose -f docker-compose.cpu.yml up -d
echo Done! Access at http://localhost:90
pause