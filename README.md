# Protocolist (Протоколист)

Professional creation of meeting protocols/minutes.

## Running the Application

### Native Windows Launch
1. Ensure Ollama is running locally.
2. Double click on `Запустить_СИСТЕМУ.bat`.
3. The script will automatically start the Backend and Frontend.

### Docker Launch
1. Open a terminal in the project directory.
2. Run `docker-compose up -d` to start the application with GPU support, or `docker-compose -f docker-compose.cpu.yml up -d` for CPU only.
3. Access the frontend at `http://localhost:90` or `http://localhost:5173`.
