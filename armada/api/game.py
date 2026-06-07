from __future__ import annotations
import uuid
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from armada.domain.factories import create_battle_state
from armada.domain.enums import Direction, ShipState, CellType, ModuleType
from armada.domain.models import BattleState, GridPos
from armada.domain.movement import MovementValidator
from armada.domain.modules import fire, apply_aa_intercept
from armada.domain.ai import AiController
from armada.domain.battle_loop import (
    begin_player_turn, end_player_turn, end_ai_turn,
    apply_damage_to_ships, check_victory, ship_at_port, ship_near_oilrig,
)

router = APIRouter(prefix="/game")

_sessions: dict[str, BattleState] = {}


class NewGameRequest(BaseModel):
    admiral_profile: str = "balanced"
    seed: int | None = None


class ActionRequest(BaseModel):
    type: str  # "move" | "move_to" | "rotate" | "fire" | "end_turn"
    ship_index: int = 0
    direction: str | None = None
    clockwise: bool = True
    module_cell_index: int | None = None
    target: dict | None = None


def _find_path(ship, target: GridPos, all_ships: list, battlefield) -> list[GridPos] | None:
    """BFS to find path from ship.bridge_pos to target. Returns ordered list of positions including target."""
    from collections import deque
    from armada.domain.enums import TerrainHeight

    start = ship.bridge_pos
    if start == target:
        return [target]

    occupied = set()
    for s in all_ships:
        if s is ship or s.state == ShipState.Dead:
            continue
        for p in s.occupied_cells():
            occupied.add((p.x, p.y))

    queue = deque([(start, [start])])
    visited = {(start.x, start.y)}
    draft = ship.draft()

    while queue:
        pos, path = queue.popleft()
        if len(path) > 32:  # Prevent infinite loops
            continue

        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = pos.x + dx, pos.y + dy
            if (nx, ny) in visited:
                continue
            if nx < 0 or nx >= 15 or ny < 1 or ny > 16:  # Player zone only
                continue

            cell = battlefield.cells.get((nx, ny))
            if not cell:
                continue
            if cell.height in (TerrainHeight.Land, TerrainHeight.Mountain):
                continue
            if draft >= 2 and cell.height == TerrainHeight.ShallowWater:
                continue
            if (nx, ny) in occupied:
                continue

            new_pos = GridPos(nx, ny)
            new_path = path + [new_pos]

            if new_pos == target:
                return new_path

            visited.add((nx, ny))
            queue.append((new_pos, new_path))

    return None


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
                    "fired_this_turn": c.fired_this_turn,
                }
                for c in ship.cells
            ],
            "moved": ship.moved_this_turn,
            "fired": ship.fired_this_turn,
            "size": len(ship.cells),
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
        "player_profile": state.player_admiral.profile,
        "player_stats": {
            "fuel_per_turn":   state.player_admiral.stats.fuel_per_turn,
            "supply_per_turn": state.player_admiral.stats.supply_per_turn,
        },
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

    if state.phase not in ("player", "ai"):
        return {"ok": False, "error": "game_over", "state": _snapshot(state)}

    if state.phase != "player":
        return {"ok": False, "error": "not_player_turn", "state": _snapshot(state)}

    victory = check_victory(state)
    if victory:
        return {"ok": False, "error": "game_over", "state": _snapshot(state)}

    player_ships = state.player_admiral.armada.ships
    ai_ships     = state.ai_admiral.armada.ships
    all_ships    = player_ships + ai_ships

    if req.type == "end_turn":
        end_player_turn(state)
        if state.phase == "ai":
            AiController.execute_turn(state)
            end_ai_turn(state)
        return {"ok": True, "error": None, "state": _snapshot(state)}

    if req.ship_index >= len(player_ships):
        return {"ok": False, "error": "invalid_ship_index", "state": _snapshot(state)}

    ship = player_ships[req.ship_index]
    if ship.state == ShipState.Dead:
        return {"ok": False, "error": "ship_dead", "state": _snapshot(state)}

    if req.type == "move_to":
        if req.target is None:
            return {"ok": False, "error": "missing_target", "state": _snapshot(state)}
        if not ship.can_move:
            return {"ok": False, "error": "cannot_move", "state": _snapshot(state)}

        target = GridPos(req.target["x"], req.target["y"])
        path = _find_path(ship, target, all_ships, state.battlefield)
        if not path:
            return {"ok": False, "error": "no_path", "state": _snapshot(state)}

        # Cost: Size for startup + 1 per cell after first
        startup_cost = len(ship.cells)
        movement_cost = len(path) - 1
        total_cost = startup_cost + movement_cost

        if not state.turn_budget.spend_fuel(total_cost):
            return {"ok": False, "error": "insufficient_fuel", "state": _snapshot(state)}

        # Move ship to target
        ship.bridge_pos = target
        ship.moved_this_turn = True
        return {"ok": True, "error": None, "state": _snapshot(state)}

    if req.type == "move":
        if req.direction is None:
            return {"ok": False, "error": "missing_direction", "state": _snapshot(state)}
        try:
            direction = Direction(req.direction)
        except ValueError:
            return {"ok": False, "error": "invalid_direction", "state": _snapshot(state)}
        if not ship.can_move:
            return {"ok": False, "error": "cannot_move", "state": _snapshot(state)}
        # OilRig adjacency: free first move
        at_oilrig = ship_near_oilrig(ship, state.battlefield)
        fuel_cost = 0 if (ship_at_port(ship, state.battlefield) or at_oilrig) and not ship.moved_this_turn else len(ship.cells)
        if not state.turn_budget.spend_fuel(fuel_cost):
            return {"ok": False, "error": "insufficient_fuel", "state": _snapshot(state)}
        if not MovementValidator.is_valid_move(ship, direction, all_ships, state.battlefield, is_player=True):
            state.turn_budget.fuel += fuel_cost
            return {"ok": False, "error": "invalid_position", "state": _snapshot(state)}
        MovementValidator.apply_move(ship, direction)
        return {"ok": True, "error": None, "state": _snapshot(state)}

    if req.type == "rotate":
        if not ship.can_move:
            return {"ok": False, "error": "cannot_move", "state": _snapshot(state)}
        fuel_cost = len(ship.cells)
        if not state.turn_budget.spend_fuel(fuel_cost):
            return {"ok": False, "error": "insufficient_fuel", "state": _snapshot(state)}
        if not MovementValidator.is_valid_rotation(ship, req.clockwise, all_ships, state.battlefield, is_player=True):
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
        if not ship.can_fire:
            return {"ok": False, "error": "cannot_fire", "state": _snapshot(state)}
        cell = ship.cells[idx]
        if cell.cell_type != CellType.Weapon or cell.hp <= 0:
            return {"ok": False, "error": "cell_not_weapon", "state": _snapshot(state)}
        if cell.fired_this_turn:
            return {"ok": False, "error": "module_already_fired", "state": _snapshot(state)}
        if cell.module_type in ship.activated_modules:
            return {"ok": False, "error": "module_type_already_activated", "state": _snapshot(state)}
        # Port: fire is free
        supply_cost = 0 if ship_at_port(ship, state.battlefield) else 1
        if not state.turn_budget.spend_supply(supply_cost):
            return {"ok": False, "error": "insufficient_supply", "state": _snapshot(state)}
        occupied = ship.occupied_cells()
        gun_pos  = occupied[idx]
        tgt = None
        if req.target:
            tgt = GridPos(req.target["x"], req.target["y"])
        impacts = fire(cell.module_type, gun_pos, ship.facing,
                       state.battlefield, all_ships, tgt, firing_ship=ship)
        impacts = [apply_aa_intercept(r, all_ships) for r in impacts]
        apply_damage_to_ships(impacts, ai_ships, state.battlefield)
        cell.fired_this_turn = True
        ship.fired_this_turn = True
        ship.activated_modules.add(cell.module_type)
        return {"ok": True, "error": None, "state": _snapshot(state)}

    return {"ok": False, "error": "unknown_action", "state": _snapshot(state)}
