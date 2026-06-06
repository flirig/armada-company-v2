# Railway setup

## Prerequisites

- Railway account (railway.app).
- Railway CLI: `npm install -g @railway/cli` or `brew install railway`.
- GitHub repo with the project.

## Initial deploy

```bash
# Login
railway login

# Create project (run from repo root)
railway init

# Add PostgreSQL plugin
railway add --plugin postgresql

# Deploy
railway up
```

Railway auto-detects the `Dockerfile` and builds it. `DATABASE_URL` is injected automatically by the PostgreSQL plugin.

## Environment variables

Set these in the Railway dashboard or via CLI:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Auto (plugin) | PostgreSQL connection string |
| `PORT` | Auto | Uvicorn listen port |
| `SECRET_KEY` | Yes | Random string for session signing |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins (defaults to `*`) |

```bash
# Set manually
railway variables set SECRET_KEY=your-random-secret
```

## Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

CMD ["sh", "-c", "uvicorn armada.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

## railway.toml

```toml
[build]
builder = "dockerfile"

[deploy]
healthcheckPath = "/healthz"
healthcheckTimeout = 10
restartPolicyType = "on_failure"
```

## Database migrations

Uses Alembic. Run migrations on deploy:

```bash
# Generate migration after model changes
alembic revision --autogenerate -m "describe change"

# Apply (run locally against Railway DB)
DATABASE_URL=<railway-db-url> alembic upgrade head
```

Add to Dockerfile CMD to auto-migrate on startup:

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn armada.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

## Local development

```bash
# Create venv
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install
pip install -e ".[dev]"

# Copy env
cp .env.example .env
# Edit .env: set DATABASE_URL to local Postgres or sqlite+aiosqlite:///./dev.db

# Run
uvicorn armada.api.main:app --reload
```

Open `http://localhost:8000` — serves `static/index.html`.

## Branching and preview envs

Railway supports preview environments per branch. Enable in Dashboard → Settings → Environments. Each PR gets its own URL with its own DB.
