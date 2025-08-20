# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_ENV=production

WORKDIR /schedule2calendar

# System deps (curl for healthchecks/logs; build tools only if you need them)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Copy and install deps
# If you use Poetry, swap these lines for `poetry install --no-root --only main`
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app
COPY . .

# Expose app port
EXPOSE 5000

# Default: run with Gunicorn (app factory is in package __init__, runner module is app.py -> app:app)
CMD ["gunicorn", "-w", "3", "-k", "gthread", "-b", "0.0.0.0:5000", "schedule2calendar.app:app"]
