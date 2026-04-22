# Bulk Email Dispatch Platform - Backend

This repository contains the backend service for the Bulk Email Dispatch Platform, providing dynamic email templating, background task processing, and WebSocket real-time dispatch monitoring.

## Tech Stack
- **Framework**: Django, Django REST Framework, Django Channels
- **Database**: PostgreSQL
- **Message Broker & Cache**: Redis
- **Async Tasks**: Celery
- **Orchestration**: Docker, Docker Compose

## Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker + Docker Compose)

## Gmail SMTP Configuration
To send emails using Gmail, generate an App Password:
1. Go to your [Google Account settings](https://myaccount.google.com/).
2. Navigate to **Security** > **2-Step Verification** > **App passwords**.
3. Create an app password and copy the 16-character code.
4. Add it to your `.env` file as `SENDER_APP_PASSWORD`.

## Getting Started

1. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   *Open `.env` and fill in your values, especially `SENDER_EMAIL` and `SENDER_APP_PASSWORD`.*

2. Create the external docker network (if not already created by frontend or manually):
   ```bash
   docker network create mail_system_net || true
   ```

3. Start the backend services:
   ```bash
   docker-compose up --build -d
   ```

## Service URLs
- **Backend API:** http://localhost:8000
- **Django Admin:** http://localhost:8000/admin

## Useful Commands
- **View Logs:** `docker-compose logs -f backend` or `docker-compose logs -f celery`
- **Django Shell:** `docker-compose exec backend python manage.py shell`
- **Create Superuser:** `docker-compose exec backend python manage.py createsuperuser`
- **Stop services:** `docker-compose down`
