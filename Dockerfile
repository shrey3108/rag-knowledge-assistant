FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
    OMP_NUM_THREADS=1 \
    PORT=8000

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Astral uv package manager
RUN pip install --no-cache-dir uv

# Copy configuration and source files required for wheel build
COPY pyproject.toml README.md ./
COPY app ./app

# Install lightweight CPU-only PyTorch first (saves ~2GB size and massive RAM)
RUN uv pip install --no-cache --index-url https://download.pytorch.org/whl/cpu torch

# Install dependencies using uv
RUN uv pip install --no-cache .

# Pre-cache embedding model at build time so runtime doesn't download it or timeout
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

# Copy remaining project files (static assets, configs, sample docs)
COPY . .

# Ensure data directory exists
RUN mkdir -p /app/data/chroma_db

EXPOSE 8000

# Bind to Render's dynamic PORT or default 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
