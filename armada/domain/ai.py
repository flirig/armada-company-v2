from __future__ import annotations
import math
from armada.domain.enums import Direction, ShipState, CellType, ModuleType
from armada.domain.models import BattleState, Ship, GridPos, _facing_delta
from armada.domain.movement import MovementValidator
from armada.domain.modules import fire, apply_aa_intercept, ImpactResult


def _dist(a: GridPos, b: GridPos) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _nearest_player_ship(ai_ship: Ship, player_ships: list[Ship]) -> Ship | None:
    alive = [s for s in player_ships if s.state != ShipState.Sunk]
    if not alive:
        return None
    return min(alive, key=lambda s: _dist(ai_ship.bridge_pos, s.bridge_pos))


def _face_toward(ship: Ship, target: GridPos) -> Direction:
    dx = target.x - ship.bridge_pos.x
    dy = target.y - ship.bridge_pos.y
    if abs(dx) >= abs(dy):
        return Direction.East if dx >= 0 else Direction.West
    return Direction.South if dy >= 0 else Direction.North


class AiController:

    @staticmethod
    def execute_turn(state: BattleState) -> list[dict]:
        """Execute AI turn, mutating state. Returns log of actions."""
        log = []
        ai_ships = [s for s in state.ai_admiral.armada.ships if s.state != ShipState.Sunk]
        player_ships = state.player_admiral.armada.ships
        all_ships = ai_ships + player_ships

        # Reset per-turn flags (done by battle_loop normally, but called here for AI)
        for ship in ai_ships:
            ship.moved_this_turn = False
            ship.fired_this_turn = False

        ai_budget_fuel = state.ai_admiral.stats.fuel_per_turn
        ai_budget_supply = state.ai_admiral.stats.supply_per_turn

        for ship in ai_ships:
            target_ship = _nearest_player_ship(ship, player_ships)
            if target_ship is None:
                continue

            # Try to fire first
            occupied = ship.occupied_cells()
            for i, cell in enumerate(ship.cells):
                if cell.cell_type != CellType.Weapon:
                    continue
                if cell.module_type == ModuleType.AaGun:
                    continue
                if cell.hp <= 0 or cell.fired_this_turn:
                    continue
                if ai_budget_supply < 1:
                    continue
                gun_pos = occupied[i]
                tgt = target_ship.bridge_pos if cell.module_type == ModuleType.BallisticMissile else None
                impacts = fire(cell.module_type, gun_pos, ship.facing,
                               state.battlefield, all_ships, tgt)
                impacts = [apply_aa_intercept(r, all_ships) for r in impacts]
                _apply_impacts(impacts, player_ships, state)
                cell.fired_this_turn = True
                ship.fired_this_turn = True
                ai_budget_supply -= 1
                log.append({"action": "fire", "module": cell.module_type.value})

            # Try to move toward player
            if not ship.fired_this_turn:
                desired = _face_toward(ship, target_ship.bridge_pos)
                fuel_cost = len(ship.cells)
                if ai_budget_fuel >= fuel_cost:
                    if MovementValidator.is_valid_move(ship, desired, all_ships, state.battlefield):
                        MovementValidator.apply_move(ship, desired)
                        ai_budget_fuel -= fuel_cost
                        log.append({"action": "move", "direction": desired.value})

        return log


def _apply_impacts(impacts: list[ImpactResult], ships: list[Ship], state: BattleState) -> None:
    from armada.domain.battle_loop import apply_damage_to_ships
    apply_damage_to_ships(impacts, ships, state.battlefield)
