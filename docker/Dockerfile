FROM python:3.11-slim

# ── System deps ────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# ── Working dir ────────────────────────────────────────────
WORKDIR /app

# ── Python deps (cache layer) ──────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── App source ─────────────────────────────────────────────
COPY src/ ./src/
COPY .env.example .env.example

# ── Data dirs ──────────────────────────────────────────────
RUN mkdir -p data/raw/kap data/raw/news data/raw/brokerage \
             data/processed data/chroma_db

# ── Runtime ────────────────────────────────────────────────
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
