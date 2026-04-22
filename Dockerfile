# ──────────────────────────────────────────────────────────────
# Backend Dockerfile — Django + Daphne (ASGI Server)
# ──────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies required for psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY . .

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Expose the backend port
EXPOSE 8000

# Default command — Daphne ASGI server (not Gunicorn)
# Daphne is required because Django Channels needs an ASGI server
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
