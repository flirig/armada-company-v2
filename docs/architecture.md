# Architecture

## Overview

```
browser
  └── HTML/JS/Canvas  ←→  FastAPI  ←→  Domain layer
                              ↕
                         PostgreSQL
```

The domain layer has **zero framework dependencies** — it is plain Python dataclasses and functions. FastAPI is a thin HTTP shell around it. This makes the domain fully unit-testable without a running server.

## Directory structure

```
armada/
├── domain/                 ← pure Python, no I/O
│   ├── models.py           ← dataclasses: Ship, ShipCell, Admiral, Armada, BattleGridCell, BattleState
│   ├── enums.py            ← CellType, ModuleType, Direction, ShipState, TerrainHeight, …
│   ├── movement.py         ← MovementValidator
│   ├── modules.py          ← ModuleSystem (fire, impact, AA intercept)
│   ├── ai.py               ← AiController
│   └── factories.py        ← Armada.create_battleship(), create_carrier(), create_random_armada()
│
├── api/                    ← FastAPI routers
│   ├── main.py             ← app factory, lifespan, CORS
│   ├── game.py             ← /game endpoints (new, action, state)
│   └── schema.py           ← Pydantic request/response models
│
├── db/                     ← SQLAlchemy async
│   ├── session.py          ← async engine + session factory
│   └── models.py           ← ORM: SavedGame, RunProgress
│
├── static/                 ← served by FastAPI StaticFiles
│   ├── index.html
│   ├── game.js             ← canvas render + API calls
│   └── style.css
│
├── Dockerfile
├── railway.toml
├── pyproject.toml
└── .env.example
```

## Request lifecycle

1. Player opens `/` → receives `index.html` + `game.js`.
2. JS calls `POST /game/new` → server creates `BattleState`, stores it in memory keyed by `session_id`, returns initial state snapshot.
3. Player actions → `POST /game/{session_id}/action` with `ActionRequest` body → server mutates `BattleState`, returns `StateSnapshot`.
4. AI turn runs server-side synchronously after each player end-turn.
5. Long-running state (runs, progression) persisted to PostgreSQL via SQLAlchemy.

## State management

`BattleState` lives in a module-level dict `SESSIONS: dict[str, BattleState]` for MVP. This is single-instance friendly and sufficient for Railway's single-replica free tier.

When persistence across restarts is needed: serialize `BattleState` to JSON (via `dataclasses.asdict`) and store in `saved_games` table.

## Railway deployment

- Single `Dockerfile`-based service.
- `DATABASE_URL` env var injected automatically by Railway's PostgreSQL plugin.
- `PORT` env var used by uvicorn (`$PORT` default 8000).
- Health check: `GET /healthz` → `{"status": "ok"}`.

See `docs/railway-setup.md` for step-by-step deploy instructions.
