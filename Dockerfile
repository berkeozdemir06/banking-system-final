# Use official Python lightweight image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies + Playwright dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browsers
RUN playwright install --with-deps chromium

# Copy application folders
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY assets/ ./assets/
COPY src/ ./src/
COPY app.py .

# Move into root to allow module imports
WORKDIR /app

# Render dynamic port and run using uvicorn
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
