# Armada Company v2 — roguelite PvE

## Concept
A turn-based PvE tactics game on a grid where the player chooses an admiral, builds an armada within a deck limit, and commands ships through fuel and supply resources.

Delivered as a **web application** — Python backend (FastAPI) + browser frontend (HTML/JS/Canvas). Hosted on **Railway**.

## Key features
- Admirals with different profiles, parameters, and abilities.
- Armadas as a separate layer of buildcrafting.
- Ships built as hull cell compositions.
- A battlefield with height levels, objects, effects, and previous-turn markers.
- Reconnaissance, limited information, and positioning.
- Roguelite progression between battles.

## Core loop
1. Choose an admiral.
2. Build an armada.
3. Enter battle.
4. Spend fuel and supply on fleet actions.
5. Win and receive a reward.
6. Upgrade the armada or the admiral.
7. Continue the run.

## Key combat rules
- MVP battlefield size: 15×15.
- Ships do not collide as a standalone mechanic.
- A maneuver is invalid if the ship's final position overlaps another ship.
- A ship cannot move after firing in the same turn.
- After the bridge is destroyed, the ship can keep firing for 2 more turns.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI |
| Game logic | Pure Python domain layer (no framework coupling) |
| API transport | REST + Server-Sent Events (SSE) for live game state push |
| Frontend | Vanilla JS + HTML5 Canvas (no build step) |
| Persistence | PostgreSQL (Railway managed) via SQLAlchemy async |
| Deployment | Railway (single service, Dockerfile) |
| Session state | In-memory per game session (Redis optional later) |

## Documentation structure
Detailed rules and subsystems are split into the `docs/` folder.
