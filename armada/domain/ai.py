from __future__ import annotations
import random
from armada.domain.enums import Direction, ShipState, CellType, ModuleType
from armada.domain.models import BattleState, Ship, GridPos, TurnBudget, _facing_delta
from armada.domain.movement import MovementValidator
from armada.domain.modules import fire, apply_aa_intercept, ImpactResult
from armada.domain.factories import AI_RNG_SEED, AI_Y_MIN, AI_Y_MAX, FIELD_WIDTH

_AI_RNG = random.Random(AI_RNG_SEED)


def _manhattan(a: GridPos, b: GridPos) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _nearest_player_ship(ai_ship: Ship, player_ships: list[Ship]) -> Ship | None:
    alive = [s for s in player_ships if s.state != ShipState.Dead]
    if not alive:
        return None
    return min(alive, key=lambda s: _manhattan(ai_ship.bridge_pos, s.bridge_pos))


def _best_missile_target(ai_ship: Ship, player_ships: list[Ship]) -> GridPos | None:
    alive = [s for s in player_ships if s.state != ShipState.Dead]
    candidates = []
    for ship in alive:
        for pos in ship.occupied_cells():
            if _manhattan(ai_ship.bridge_pos, pos) <= 10:
                candidates.append(pos)
    if not candidates:
        return None
    return min(candidates, key=lambda p: _manhattan(ai_ship.bridge_pos, p))


def _prioritized_directions(ai_pos: GridPos, target_pos: GridPos) -> list[Direction]:
    dx = target_pos.x - ai_pos.x
    dy = target_pos.y - ai_pos.y
    ns = Direction.South if dy > 0 else Direction.North
    ew = Direction.East  if dx > 0 else Direction.West
    if abs(dy) >= abs(dx):
        return [ns, ew]
    return [ew, ns]


class AiController:

    @staticmethod
    def execute_turn(state: BattleState) -> list[dict]:
        log: list[dict] = []
        ai_ships = [s for s in state.ai_admiral.armada.ships if s.state != ShipState.Dead]
        player_ships = state.player_admiral.armada.ships
        all_ships = ai_ships + player_ships

        ai_fuel   = state.ai_admiral.stats.fuel_per_turn
        ai_supply = state.ai_admiral.stats.supply_per_turn

        for ship in ai_ships:
            target_ship = _nearest_player_ship(ship, player_ships)

            # TryFire
            occupied = ship.occupied_cells()
            for i, cell in enumerate(ship.cells):
                if cell.cell_type != CellType.Weapon:
                    continue
                if cell.module_type == ModuleType.AaGun:
                    continue
                if cell.hp <= 0 or cell.fired_this_turn:
                    continue
                if cell.module_type in ship.activated_modules:
                    continue
                if ai_supply < 1:
                    continue
                gun_pos = occupied[i]
                tgt = None
                if cell.module_type == ModuleType.BallisticMissile:
                    tgt = _best_missile_target(ship, player_ships)
                    if tgt is None:
                        continue
                impacts = fire(cell.module_type, gun_pos, ship.facing,
                               state.battlefield, all_ships, tgt)
                impacts = [apply_aa_intercept(r, all_ships) for r in impacts]
                _apply_impacts(impacts, player_ships, state)
                cell.fired_this_turn = True
                ship.fired_this_turn = True
                ship.activated_modules.add(cell.module_type)
                ai_supply -= 1
                log.append({"action": "fire", "module": cell.module_type.value})

            # TryMove
            if target_ship is None:
                continue
            fuel_cost = len(ship.cells)
            if not ship.can_move or ai_fuel < fuel_cost:
                continue
            dirs = _prioritized_directions(ship.bridge_pos, target_ship.bridge_pos)
            for d in dirs:
                # Restrict to AI zone
                new_bridge = GridPos(
                    ship.bridge_pos.x + _facing_delta(d)[0],
                    ship.bridge_pos.y + _facing_delta(d)[1],
                )
                if new_bridge.y < AI_Y_MIN or new_bridge.y > AI_Y_MAX:
                    continue
                if MovementValidator.is_valid_move(ship, d, all_ships, state.battlefield, is_player=False):
                    MovementValidator.apply_move(ship, d)
                    ai_fuel -= fuel_cost
                    log.append({"action": "move", "direction": d.value})
                    break

        return log


def _apply_impacts(impacts: list[ImpactResult], ships: list[Ship], state: BattleState) -> None:
    from armada.domain.battle_loop import apply_damage_to_ships
    apply_damage_to_ships(impacts, ships, state.battlefield)
