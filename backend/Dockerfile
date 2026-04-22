# Use an official Python runtime as a parent image
FROM python:3.11

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    libgomp1 \
    build-essential \
    cmake \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Point HuggingFace to a writable directory within /app
ENV HF_HOME=/app/models_cache/huggingface
ENV XDG_CACHE_HOME=/app/models_cache/xdg
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib:/usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.11/site-packages/nvidia/cuda_nvrtc/lib

# Create a non-root user and group with a home directory
RUN groupadd -r appgroup && useradd -m -r -g appgroup appuser

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir fastapi uvicorn pydantic python-dotenv loguru httpx && \
    pip install --no-cache-dir faster-whisper==1.2.1 ollama==0.6.1 && \
    pip install --no-cache-dir -r requirements.txt

# --- PRE-DOWNLOAD MODELS FOR OFFLINE USE ---
# This happens during build time. Requires internet.
ARG HF_TOKEN
ENV HF_TOKEN=${HF_TOKEN}
ENV WHISPER_MODEL=medium

# Copy only the scripts needed for download to avoid rebuilding cache on every code change
COPY scripts/pre_download_models.py scripts/
RUN if [ -n "$HF_TOKEN" ]; then \
        python scripts/pre_download_models.py; \
    else \
        echo "Building without HF_TOKEN. Models will be downloaded at runtime if needed."; \
    fi

# Copy the rest of the application code
COPY . .

# Create directories and set correct ownership
RUN mkdir -p uploads temp_protocols logs && \
    chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Run uvicorn on container startup
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
