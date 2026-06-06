# Open questions

All questions below are resolved for MVP.

---

## 1. Session storage

**Decision:** in-memory dict `SESSIONS: dict[str, BattleState]` on the single Railway instance.

Rationale: Railway free tier runs one replica. This is sufficient for MVP and avoids Redis complexity. When multi-instance scaling is needed, move to Redis with `pickle` or JSON serialization of `BattleState`.

---

## 2. Frontend framework

**Decision:** vanilla JS + HTML5 Canvas, no build step.

Rationale: served directly from `static/` via FastAPI `StaticFiles`. Zero build tooling, zero dependencies, trivial Railway deploy. If the UI grows complex, migrate to a separate Vite/React service on Railway.

---

## 3. SQLite vs PostgreSQL for MVP

**Decision:** `sqlite+aiosqlite:///./dev.db` locally, Railway PostgreSQL plugin in production.

Alembic migrations work with both. Switch is just a `DATABASE_URL` change.

---

## 4. Draft-to-height traversal

Resolved — see [combat-rules.md](combat-rules.md).

| Draft | Deep sea | Shallow water | Land | Mountain |
|-------|----------|---------------|------|----------|
| 1 — light  | ✓ | ✓ | ✗ | ✗ |
| 2 — medium | ✓ | ✗ | ✗ | ✗ |
| 3 — heavy  | ✓ | ✗ | ✗ | ✗ |

---

## 5. Movement validation — step-by-step or final position only

**Decision:** final position only. Intermediate cells are not checked. See [combat-rules.md](combat-rules.md).

---

## 6. AI turn timing

**Decision:** AI turn runs synchronously inside `POST /game/{id}/action` when `type = "end_turn"`. Response returns full state after AI completes. No SSE needed for MVP.

If AI becomes slow (many ships, complex targeting): move to background task + SSE push.

---

## 7. Sprite delivery

**Decision:** sprites are static PNG files served from `static/sprites/`. The Python sprite generation toolchain from `Sprites/armada_tools/` is unchanged — it outputs 64×64 PNGs that are copied to `static/sprites/modules/` and `static/sprites/tiles/`.

Canvas renderer uses an `Image` preload map keyed by sprite name, falling back to colored rectangles for missing sprites.
