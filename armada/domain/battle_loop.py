from __future__ import annotations
from armada.domain.enums import ShipState, CellType, CellObjectType, CellEffectType, MarkerType
from armada.domain.models import BattleState, Ship, ShipCell, GridPos, Battlefield
from armada.domain.modules import ImpactResult
from armada.domain.factories import (
    BUFFER_Y_MIN, BUFFER_Y_MAX, PLAYER_Y_MAX, AI_Y_MIN,
)


def begin_player_turn(state: BattleState) -> None:
    state.turn_budget.fuel   = state.player_admiral.stats.fuel_per_turn
    state.turn_budget.supply = state.player_admiral.stats.supply_per_turn
    _reset_ship_flags(state.player_admiral.armada.ships)
    state.phase = "player"


def _reset_ship_flags(ships: list[Ship]) -> None:
    for ship in ships:
        ship.moved_this_turn  = False
        ship.fired_this_turn  = False
        ship.activated_modules = set()
        for c in ship.cells:
            c.fired_this_turn = False


def _clear_all_markers(state: BattleState) -> None:
    for cell in state.battlefield.cells.values():
        cell.markers.clear()


def _tick_dying_ships(ships: list[Ship]) -> None:
    for ship in ships:
        if ship.state == ShipState.Dying:
            ship.dying_turns_left -= 1
            if ship.dying_turns_left <= 0:
                ship.state = ShipState.Dead


def _tick_mines(state: BattleState) -> None:
    bf = state.battlefield
    all_ships = state.player_admiral.armada.ships + state.ai_admiral.armada.ships

    mine_cells = [(pos, cell) for pos, cell in bf.cells.items()
                  if cell.obj == CellObjectType.Mine]

    for pos, mine_cell in mine_cells:
        x, y = pos
        # Move toward buffer (Y=15-16)
        if y >= AI_Y_MIN:
            # AI zone: move toward buffer (decreasing y)
            new_y = y - 1
        else:
            # Player zone: move toward buffer (increasing y)
            new_y = y + 1

        # Remove from current position
        mine_cell.obj = None

        new_pos = (x, new_y)
        if new_pos not in bf.cells:
            continue

        new_cell = bf.cells[new_pos]

        # Detonate on another mine
        if new_cell.obj == CellObjectType.Mine:
            new_cell.obj = None
            continue

        # Detonate on ship
        hit_ships = [s for s in all_ships
                     if s.state != ShipState.Dead
                     and any(p.x == x and p.y == new_y for p in s.occupied_cells())]
        if hit_ships:
            for ship in hit_ships:
                for cell in ship.cells:
                    cell.apply_damage(3)
                _check_bridge_destruction(ship)
            continue

        # Move mine to new cell
        new_cell.obj = CellObjectType.Mine


def _check_bridge_destruction(ship: Ship) -> None:
    bridge = ship.cells[0]
    if bridge.hp <= 0 and ship.state == ShipState.Active:
        ship.state = ShipState.Dying
        ship.dying_turns_left = 2


def check_victory(state: BattleState) -> str | None:
    player_alive = any(s.state == ShipState.Active or s.state == ShipState.Dying
                       for s in state.player_admiral.armada.ships)
    ai_alive = any(s.state == ShipState.Active or s.state == ShipState.Dying
                   for s in state.ai_admiral.armada.ships)
    if not ai_alive:
        return "player"
    if not player_alive:
        return "ai"
    return None


def end_player_turn(state: BattleState) -> None:
    _clear_all_markers(state)
    _tick_dying_ships(state.player_admiral.armada.ships)
    _tick_dying_ships(state.ai_admiral.armada.ships)
    _tick_mines(state)
    victory = check_victory(state)
    if victory:
        state.phase = "done"
        return
    # Reset AI ship flags before AI acts
    _reset_ship_flags(state.ai_admiral.armada.ships)
    _apply_port_repairs(state)
    state.phase = "ai"


def end_ai_turn(state: BattleState) -> None:
    _clear_all_markers(state)
    _tick_dying_ships(state.player_admiral.armada.ships)
    _tick_dying_ships(state.ai_admiral.armada.ships)
    _tick_mines(state)
    victory = check_victory(state)
    if victory:
        state.phase = "done"
        return
    _reset_ship_flags(state.player_admiral.armada.ships)
    _apply_port_repairs(state)
    state.turn_number += 1
    # Refill player budget
    state.turn_budget.fuel   = state.player_admiral.stats.fuel_per_turn
    state.turn_budget.supply = state.player_admiral.stats.supply_per_turn
    state.phase = "player"


def apply_damage_to_ships(
    impacts: list[ImpactResult],
    ships: list[Ship],
    battlefield: Battlefield,
) -> None:
    occupied_map: dict[tuple[int, int], tuple[Ship, int]] = {}
    for ship in ships:
        if ship.state == ShipState.Dead:
            continue
        for i, pos in enumerate(ship.occupied_cells()):
            occupied_map[(pos.x, pos.y)] = (ship, i)

    for impact in impacts:
        key = (impact.pos.x, impact.pos.y)
        if impact.damage <= 0:
            bf_cell = battlefield.cells.get(key)
            if bf_cell:
                bf_cell.markers.append(MarkerType.Miss)
            continue
        if key in occupied_map:
            ship, cell_idx = occupied_map[key]
            cell = ship.cells[cell_idx]
            cell.apply_damage(impact.damage)
            bf_cell = battlefield.cells.get(key)
            if bf_cell:
                bf_cell.markers.append(MarkerType.Hit)
            # Bridge destruction -> Dying
            if cell.cell_type == CellType.Bridge and cell.hp <= 0:
                _check_bridge_destruction(ship)
            _handle_obj_hit(impact.pos, battlefield)
        else:
            bf_cell = battlefield.cells.get(key)
            if bf_cell:
                bf_cell.markers.append(MarkerType.Miss)
            _handle_obj_hit(impact.pos, battlefield)


def _handle_obj_hit(pos: GridPos, battlefield: Battlefield) -> None:
    key = (pos.x, pos.y)
    bf_cell = battlefield.cells.get(key)
    if bf_cell and bf_cell.obj == CellObjectType.OilRig:
        bf_cell.obj = None
        for nx, ny in [(pos.x+1,pos.y),(pos.x-1,pos.y),(pos.x,pos.y+1),(pos.x,pos.y-1)]:
            n = battlefield.cells.get((nx, ny))
            if n and CellEffectType.Fire not in n.effects:
                n.effects.append(CellEffectType.Fire)
    elif bf_cell and bf_cell.obj == CellObjectType.Mine:
        bf_cell.obj = None


def _apply_port_repairs(state: BattleState) -> None:
    """Repair all ships standing ON a port cell (+1 HP per cell)."""
    for ship in (state.player_admiral.armada.ships + state.ai_admiral.armada.ships):
        if ship.state == ShipState.Dead:
            continue
        for pos in ship.occupied_cells():
            cell = state.battlefield.cells.get((pos.x, pos.y))
            if cell and cell.obj == CellObjectType.Port:
                for c in ship.cells:
                    if c.hp < c.hp_max:
                        c.hp = min(c.hp_max, c.hp + 1)
                break  # one repair per ship per turn


def ship_at_port(ship: Ship, battlefield: Battlefield) -> bool:
    """Return True if any cell of the ship stands on a Port."""
    for pos in ship.occupied_cells():
        cell = battlefield.cells.get((pos.x, pos.y))
        if cell and cell.obj == CellObjectType.Port:
            return True
    return False


def ship_near_oilrig(ship: Ship, battlefield: Battlefield) -> bool:
    """Return True if any cell of the ship is orthogonally adjacent to an OilRig."""
    for pos in ship.occupied_cells():
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nb = battlefield.cells.get((pos.x+dx, pos.y+dy))
            if nb and nb.obj == CellObjectType.OilRig:
                return True
    return False
