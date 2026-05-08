@echo off
echo Packing EVERYTHING for maximum autonomy... This will take 10-15 minutes.
docker save meetingprotocolcreator-backend:latest -o images/backend.tar
echo Backend done...
docker save meetingprotocolcreator-frontend:latest -o images/frontend.tar
echo Frontend done...
docker save ollama/ollama:latest -o images/ollama.tar
echo Ollama done!
echo DONE! Your USB drive is now a complete standalone server.
pause