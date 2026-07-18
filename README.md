# Bulk Email Dispatch Platform - Backend

Django / DRF / Channels backend for dynamic email templating, Celery dispatch, and real-time progress. Application authentication uses [Clerk](https://clerk.com) session tokens. Django’s built-in `/admin/` staff login remains separate.

## Tech Stack
- **Framework**: Django, Django REST Framework, Django Channels
- **Auth**: Clerk (`clerk-backend-api`) + local `ClerkIdentity` mapping
- **Database**: PostgreSQL
- **Message Broker & Cache**: Redis
- **Async Tasks**: Celery
- **Orchestration**: Docker, Docker Compose

## Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker + Docker Compose)
- Clerk secret key (and optionally JWT PEM public key)

## Environment

```bash
cp .env.example .env
```

Required variables:

| Variable | Description |
|---|---|
| `DOMAIN` | Public hostname for Caddy TLS via nip.io (e.g. `13-60-91-88.nip.io` for IP `13.60.91.88`) |
| `CLERK_SECRET_KEY` | Backend secret key (`sk_test_...` / `sk_live_...`) |
| `CLERK_JWT_KEY` | Optional PEM public key for networkless verification (`\n` for newlines) |
| `CLERK_AUTHORIZED_PARTIES` | Comma-separated frontend origins allowed in token `azp` |
| `CORS_ALLOWED_ORIGINS` | Browser origins allowed for REST (include `https://mailblasto.vercel.app`) |
| `WS_ALLOWED_ORIGINS` | Browser `Origin` values allowed for WebSockets (scheme + host) |
| `CSRF_TRUSTED_ORIGINS` | Trusted CSRF origins (must include the HTTPS frontend) |
| `CREDENTIALS_ENCRYPTION_KEY` | Fernet key used to encrypt each user's Gmail app password |

Generate an encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

SMTP sender accounts are **per user**:
- Sender email is locked to the Clerk signup email
- Each user enters their Gmail App Password in the frontend **Settings** page

## Getting Started

1. Configure `.env` (see above).
2. Create the shared Docker network:
   ```bash
   docker network create mail_system_net || true
   ```
3. Start services:
   ```bash
   docker-compose up --build -d
   ```

## Auth model
- DRF defaults: `ClerkAuthentication` + `IsAuthenticated`
- Local `ClerkIdentity` maps Clerk `sub` → Django `User` (unusable password, never auto-staff)
- Templates and jobs are scoped to `request.user`
- Dispatch uses the job owner's encrypted SMTP credentials
- WebSockets require a first-message Clerk token and job ownership check
- `/admin/` continues to use Django session authentication for staff users

## Service URLs
- **Backend API (local):** http://localhost:8000
- **Django Admin (local):** http://localhost:8000/admin
- **Health check:** `/api/health/`
- **Production (Caddy TLS via nip.io):** `https://13-60-91-88.nip.io` (replace with your VM IP)

## Production: HTTPS for Vercel ↔ AWS (no custom DNS)

Browsers block **mixed content**: an HTTPS frontend (Vercel) cannot call an HTTP API or open `ws://` WebSockets. The AWS VM must expose the backend over **HTTPS/WSS** via Caddy.

You do **not** need to manage DNS or create A records. Use [nip.io](https://nip.io): it resolves `<ip-with-dashes>.nip.io` to that IP automatically (e.g. `13.60.91.88` → `13-60-91-88.nip.io`). Vercel calls that HTTPS/WSS origin directly.

### AWS prerequisites
1. Prefer an **Elastic IP** on the VM so the nip.io hostname stays stable when the instance restarts.
2. Open inbound **TCP 80** and **TCP 443** on the VM security group (Caddy needs 80 for ACME + 443 for TLS).
3. Convert the public IP to nip.io form (`tr . -`) and set VM `.env`:

```bash
# Public IP 13.60.91.88 → DOMAIN=13-60-91-88.nip.io
DOMAIN=13-60-91-88.nip.io
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=13-60-91-88.nip.io,localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=https://mailblasto.vercel.app
WS_ALLOWED_ORIGINS=https://mailblasto.vercel.app
CSRF_TRUSTED_ORIGINS=https://mailblasto.vercel.app
CLERK_AUTHORIZED_PARTIES=https://mailblasto.vercel.app
```

(Keep local `http://localhost:*` origins in those lists if you still develop against the same VM.)

4. Deploy with `docker-compose up --build -d` (or the GitHub Actions CI/CD pipeline). Caddy obtains a Let's Encrypt certificate for `DOMAIN`.
5. Verify:

```bash
curl -fsS https://13-60-91-88.nip.io/api/health/
# → {"status":"ok"}
```

### Vercel frontend env
Set these in the Vercel project (Production) — same nip.io host as `DOMAIN`:

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://13-60-91-88.nip.io` |
| `VITE_WS_BASE_URL` | `wss://13-60-91-88.nip.io` (optional; derived from API URL if omitted) |
| `VITE_CLERK_PUBLISHABLE_KEY` | your Clerk publishable key |

Also allow `https://mailblasto.vercel.app` in the Clerk Dashboard allowed origins / redirect URLs.

## Useful Commands
- **Tests:** `python manage.py test --settings=config.test_settings`
- **View Logs:** `docker-compose logs -f backend` or `docker-compose logs -f celery`
- **Django Shell:** `docker-compose exec backend python manage.py shell`
- **Create Superuser:** `docker-compose exec backend python manage.py createsuperuser`
- **Stop services:** `docker-compose down`

## Troubleshooting: Gmail SMTP (`timed out` / network firewall)

Dispatch uses Gmail SMTP on **outbound TCP 587** (`smtp.gmail.com`). Celery runs with `network_mode: host`, so if connects time out, the **host firewall or ISP** is usually blocking client SMTP — not bad app passwords.

Allow outbound **TCP 587** (and ideally **465**) on the host, then verify:

```bash
# 1) From the host
python3 -c "import socket; s=socket.create_connection(('smtp.gmail.com',587),timeout=10); print('host OK', s.getpeername()); s.close()"

# 2) From the host-network Celery container
docker-compose exec -T celery python -c "import socket; s=socket.create_connection(('smtp.gmail.com',587),timeout=10); print('celery OK', s.getpeername()); s.close()"
```

- Success prints `host OK` / `celery OK` with a peer address.
- `TimeoutError` / “timed out” means 587 is still blocked; opening a local app-password setting will not help until the probe succeeds.
- After both probes succeed, run a **1-row** CSV dispatch from the UI. A wrong app password surfaces as `SMTPAuthenticationError`, which is distinct from a connect timeout.
