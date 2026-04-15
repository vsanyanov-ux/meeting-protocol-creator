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

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages
# Install packages in chunks to avoid Out of Memory during build
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir fastapi uvicorn pydantic python-dotenv loguru httpx && \
    pip install --no-cache-dir faster-whisper==1.2.1 ollama==0.6.1 && \
    pip install --no-cache-dir -r requirements.txt

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
