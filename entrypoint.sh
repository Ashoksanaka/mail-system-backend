#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Backend Entrypoint Script
# Runs Django migrations before launching the ASGI server
# ──────────────────────────────────────────────────────────────
set -e

echo "⏳ Waiting for database..."
python manage.py migrate --noinput
echo "✅ Migrations complete."

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput
echo "✅ Static files collected."

echo "🚀 Starting Daphne ASGI server..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
