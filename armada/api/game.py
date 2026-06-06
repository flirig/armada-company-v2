from __future__ import annotations
import uuid
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from armada.domain.factories import create_battle_state
from armada.domain.enums import Direction, ShipState, CellType
from armada.domain.models import BattleState, GridPos
from armada.domain.movement import MovementValidator
from armada.domain.modules import fire, apply_aa_intercept
from armada.domain.ai import AiController
from armada.domain.battle_loop import (
    begin_player_turn, end_player_turn, apply_damage_to_ships, check_victory
)

router = APIRouter(prefix="/game")

# In-memory session store
_sessions: dict[str, BattleState] = {}


class NewGameRequest(BaseModel):
    admiral_profile: str = "balanced"
    seed: int | None = None


class ActionRequest(BaseModel):
    type: str  # "move" | "rotate" | "fire" | "end_turn"
    ship_index: int = 0
    direction: str | None = None  # N/E/S/W for move/rotate
    clockwise: bool = True  # for rotate
    module_cell_index: int | None = None  # for fire
    target: dict | None = None  # for ballistic_missile


def _snapshot(state: BattleState) -> dict:
    victory = check_victory(state)

    def ship_dict(ship, idx):
        return {
            "index": idx,
            "bridge_pos": {"x": ship.bridge_pos.x, "y": ship.bridge_pos.y},
            "facing": ship.facing.value,
            "state": ship.state.value,
            "cells": [
                {
                    "type": c.cell_type.value,
                    "module": c.module_type.value if c.module_type else None,
                    "hp": c.hp,
                    "hp_max": c.hp_max,
                }
                for c in ship.cells
            ],
            "moved": ship.moved_this_turn,
            "fired": ship.fired_this_turn,
        }

    grid = []
    for (x, y), cell in state.battlefield.cells.items():
        grid.append({
            "x": x, "y": y,
            "height": cell.height.value if hasattr(cell.height, "value") else cell.height,
            "obj": cell.obj.value if cell.obj else None,
            "effects": [e.value for e in cell.effects],
            "markers": [m.value for m in cell.markers],
        })

    return {
        "turn_number": state.turn_number,
        "phase": state.phase,
        "budget": {"fuel": state.turn_budget.fuel, "supply": state.turn_budget.supply},
        "player_ships": [ship_dict(s, i) for i, s in enumerate(state.player_admiral.armada.ships)],
        "ai_ships": [ship_dict(s, i) for i, s in enumerate(state.ai_admiral.armada.ships)],
        "grid": grid,
        "victory": victory,
    }


@router.post("/new")
async def new_game(req: NewGameRequest):
    state = create_battle_state(req.admiral_profile, req.seed)
    session_id = str(uuid.uuid4())
    _sessions[session_id] = state
    return {"session_id": session_id, "state": _snapshot(state)}


@router.get("/{session_id}/state")
async def get_state(session_id: str):
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    return _snapshot(state)


@router.post("/{session_id}/action")
async def action(session_id: str, req: ActionRequest):
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    if state.phase != "player":
        return {"ok": False, "error": "not_player_turn", "state": _snapshot(state)}

    victory = check_victory(state)
    if victory:
        return {"ok": False, "error": "game_over", "state": _snapshot(state)}

    player_ships = state.player_admiral.armada.ships
    ai_ships = state.ai_admiral.armada.ships
    all_ships = player_ships + ai_ships

    if req.type == "end_turn":
        end_player_turn(state)
        AiController.execute_turn(state)
        state.turn_number += 1
        begin_player_turn(state)
        return {"ok": True, "error": None, "state": _snapshot(state)}

    if req.ship_index >= len(player_ships):
        return {"ok": False, "error": "invalid_ship_index", "state": _snapshot(state)}

    ship = player_ships[req.ship_index]
    if ship.state == ShipState.Sunk:
        return {"ok": False, "error": "ship_sunk", "state": _snapshot(state)}

    if req.type == "move":
        if req.direction is None:
            return {"ok": False, "error": "missing_direction", "state": _snapshot(state)}
        try:
            direction = Direction(req.direction)
        except ValueError:
            return {"ok": False, "error": "invalid_direction", "state": _snapshot(state)}
        fuel_cost = len(ship.cells)
        if ship.moved_this_turn:
            return {"ok": False, "error": "already_moved", "state": _snapshot(state)}
        if ship.fired_this_turn:
            return {"ok": False, "error": "already_fired", "state": _snapshot(state)}
        if not state.turn_budget.spend_fuel(fuel_cost):
            return {"ok": False, "error": "insufficient_fuel", "state": _snapshot(state)}
        if not MovementValidator.is_valid_move(ship, direction, all_ships, state.battlefield):
            state.turn_budget.fuel += fuel_cost  # refund
            return {"ok": False, "error": "invalid_position", "state": _snapshot(state)}
        MovementValidator.apply_move(ship, direction)
        return {"ok": True, "error": None, "state": _snapshot(state)}

    if req.type == "rotate":
        fuel_cost = len(ship.cells)
        if ship.fired_this_turn:
            return {"ok": False, "error": "already_fired", "state": _snapshot(state)}
        if not state.turn_budget.spend_fuel(fuel_cost):
            return {"ok": False, "error": "insufficient_fuel", "state": _snapshot(state)}
        if not MovementValidator.is_valid_rotation(ship, req.clockwise, all_ships, state.battlefield):
            state.turn_budget.fuel += fuel_cost
            return {"ok": False, "error": "invalid_rotation", "state": _snapshot(state)}
        MovementValidator.apply_rotation(ship, req.clockwise)
        return {"ok": True, "error": None, "state": _snapshot(state)}

    if req.type == "fire":
        if req.module_cell_index is None:
            return {"ok": False, "error": "missing_module", "state": _snapshot(state)}
        idx = req.module_cell_index
        if idx >= len(ship.cells):
            return {"ok": False, "error": "invalid_cell", "state": _snapshot(state)}
        cell = ship.cells[idx]
        if cell.cell_type != CellType.Weapon or cell.hp <= 0:
            return {"ok": False, "error": "cell_not_weapon", "state": _snapshot(state)}
        if cell.fired_this_turn:
            return {"ok": False, "error": "module_already_fired", "state": _snapshot(state)}
        if not state.turn_budget.spend_supply():
            return {"ok": False, "error": "insufficient_supply", "state": _snapshot(state)}
        occupied = ship.occupied_cells()
        gun_pos = occupied[idx]
        tgt = None
        if req.target:
            tgt = GridPos(req.target["x"], req.target["y"])
        impacts = fire(cell.module_type, gun_pos, ship.facing,
                       state.battlefield, all_ships, tgt)
        impacts = [apply_aa_intercept(r, all_ships) for r in impacts]
        apply_damage_to_ships(impacts, ai_ships, state.battlefield)
        cell.fired_this_turn = True
        ship.fired_this_turn = True
        return {"ok": True, "error": None, "state": _snapshot(state)}

    return {"ok": False, "error": "unknown_action", "state": _snapshot(state)}
