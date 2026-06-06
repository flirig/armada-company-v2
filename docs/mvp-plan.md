# MVP plan

## Backend (domain + API)

- [ ] `enums.py` — all enums.
- [ ] `models.py` — all dataclasses.
- [ ] `factories.py` — ship factories + `create_random_armada`.
- [ ] `movement.py` — `MovementValidator` (move + rotate, final-position check).
- [ ] `modules.py` — `ModuleSystem.fire()` for all 5 modules + AA intercept.
- [ ] `ai.py` — `AiController.execute_turn()` (fire nearest, move toward player).
- [ ] `battle_loop.py` — turn lifecycle: refill budget, apply dying-ship countdown, clear markers, check victory.
- [ ] `api/game.py` — `POST /game/new`, `GET /game/{id}/state`, `POST /game/{id}/action`.
- [ ] `api/main.py` — app factory, static file serving, CORS, `/healthz`.

## Frontend (Canvas)

- [ ] 15×15 grid render (terrain colors / sprites).
- [ ] Ship cell rendering (sprite or color rect).
- [ ] Click-to-select ship → highlight.
- [ ] Action buttons: Move (WASD or arrow), Rotate (Q/E), Fire (module list), End Turn.
- [ ] HUD: turn number, fuel bar, supply counter.
- [ ] Previous-turn markers overlay.
- [ ] Victory / defeat screen.

## Infrastructure

- [ ] `Dockerfile`.
- [ ] `railway.toml`.
- [ ] `pyproject.toml` (dependencies).
- [ ] `.env.example`.
- [ ] Alembic setup (even if SQLite for MVP).
- [ ] Deploy to Railway.

## Later

- [ ] Custom admiral builder.
- [ ] Roguelite run map.
- [ ] Progression rewards.
- [ ] Turn history / replay.
- [ ] Advanced effects (ice movement penalty, storm range penalty, fog hide).
- [ ] PostgreSQL (replace SQLite).
- [ ] Preview environments per branch.
