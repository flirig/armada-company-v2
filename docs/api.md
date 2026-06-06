# API reference

Base URL: `https://<railway-service>.up.railway.app`

All endpoints return JSON. Errors return `{"detail": "..."}` with the appropriate HTTP status.

---

## Health

### `GET /healthz`
Returns `{"status": "ok"}`. Used by Railway's health check.

---

## Game session

### `POST /game/new`

Create a new battle session.

**Request body:**
```json
{
  "admiral_profile": "balanced",   // "mobile" | "offensive" | "heavy" | "recon" | "balanced"
  "seed": 42                        // optional, for reproducible AI armada
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "state": { ... }   // StateSnapshot (see below)
}
```

---

### `GET /game/{session_id}/state`

Fetch current game state without performing any action.

**Response:** `StateSnapshot`

---

### `POST /game/{session_id}/action`

Perform one player action.

**Request body:** `ActionRequest`

```json
{
  "type": "move",          // "move" | "rotate" | "fire" | "end_turn"
  "ship_index": 0,         // index in player armada
  "direction": "N",        // for move/rotate
  "module_cell_index": 2,  // for fire
  "target": {"x": 10, "y": 7}  // for ballistic_missile
}
```

**Response:**
```json
{
  "ok": true,
  "error": null,           // or "insufficient_fuel" | "already_fired" | "invalid_position" | …
  "state": { ... }         // updated StateSnapshot after action + AI turn if end_turn
}
```

---

## StateSnapshot schema

```json
{
  "turn_number": 1,
  "phase": "player",
  "budget": { "fuel": 5, "supply": 5 },
  "player_ships": [
    {
      "index": 0,
      "bridge_pos": { "x": 3, "y": 7 },
      "facing": "E",
      "state": "alive",
      "cells": [
        { "type": "bridge", "module": null, "hp": 3, "hp_max": 3 },
        { "type": "weapon", "module": "torpedo", "hp": 2, "hp_max": 2 }
      ],
      "moved": false,
      "fired": false
    }
  ],
  "ai_ships": [ ... ],     // same shape; weapon cell hp hidden if in fog
  "grid": [
    {
      "x": 0, "y": 0,
      "height": "deep_sea",
      "obj": null,
      "effects": [],
      "markers": []
    },
    ...
  ],
  "victory": null           // null | "player" | "ai"
}
```

---

## Run progression

### `POST /run/new`
Start a new roguelite run. Returns `{"run_id": "uuid", "map": [...]}`.

### `GET /run/{run_id}`
Fetch run state (current node, admiral, credits).

### `POST /run/{run_id}/reward`
Apply chosen reward. Body: `{"choice": 0}` (index into reward list).

### `POST /run/{run_id}/advance`
Advance to next map node.
