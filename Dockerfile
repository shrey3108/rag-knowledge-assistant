FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
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

# Install dependencies using uv
RUN uv pip install --no-cache .

# Copy remaining project files (static assets, configs, sample docs)
COPY . .

# Ensure data directory exists
RUN mkdir -p /app/data/chroma_db

EXPOSE 8000

# Bind to Render's dynamic PORT or default 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
