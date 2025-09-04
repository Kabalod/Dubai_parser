# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . .

# Collect static during build (non-fatal if DEBUG true)
RUN python manage.py collectstatic --noinput || true

# Expose runtime port (Railway sets $PORT)
EXPOSE 8000

# Healthcheck (optional)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT:-8000}/ || exit 1

# Default envs (overridable by Railway)
ENV DEBUG=False

# Entrypoint: run migrations and start gunicorn bound to $PORT
CMD python manage.py migrate --noinput && \
    gunicorn property_analyzer.wsgi:application \
      --bind 0.0.0.0:${PORT:-8000} \
      --workers 3 \
      --timeout 60 \
      --log-level info
