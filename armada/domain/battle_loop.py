from __future__ import annotations
from armada.domain.enums import ShipState, CellType, CellObjectType, CellEffectType, MarkerType
from armada.domain.models import BattleState, Ship, GridPos, Battlefield
from armada.domain.modules import ImpactResult


def begin_player_turn(state: BattleState) -> None:
    """Refill budget, clear markers, decrement dying ships."""
    state.turn_budget.fuel = state.player_admiral.stats.fuel_per_turn
    state.turn_budget.supply = state.player_admiral.stats.supply_per_turn
    # Clear previous-turn markers
    for cell in state.battlefield.cells.values():
        cell.markers.clear()
    # Reset per-turn ship flags
    for ship in state.player_admiral.armada.ships:
        ship.moved_this_turn = False
        ship.fired_this_turn = False
        for c in ship.cells:
            c.fired_this_turn = False
    # Advance dying ships
    _tick_dying_ships(state.player_admiral.armada.ships)
    _tick_dying_ships(state.ai_admiral.armada.ships)
    state.phase = "player"


def _tick_dying_ships(ships: list[Ship]) -> None:
    for ship in ships:
        if ship.state == ShipState.Dying:
            ship.dying_turns_left -= 1
            if ship.dying_turns_left <= 0:
                ship.state = ShipState.Sunk


def apply_damage_to_ships(
    impacts: list[ImpactResult],
    ships: list[Ship],
    battlefield: Battlefield,
) -> None:
    occupied_map: dict[tuple[int, int], tuple[Ship, int]] = {}
    for ship in ships:
        if ship.state == ShipState.Sunk:
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
            dmg = impact.damage
            # Armor reduction: check adjacent armor cells (simplified: any armor cell)
            has_armor = any(c.cell_type == CellType.Armor and c.hp > 0 for c in ship.cells)
            if has_armor:
                dmg = max(1, dmg - 1)
            cell.hp = max(0, cell.hp - dmg)
            bf_cell = battlefield.cells.get(key)
            if bf_cell:
                bf_cell.markers.append(MarkerType.Hit)
            # Check bridge destruction
            if cell.cell_type == CellType.Bridge and cell.hp <= 0:
                if ship.state == ShipState.Alive:
                    ship.state = ShipState.Dying
                    ship.dying_turns_left = 2
            # Handle object destruction
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
        # already handled by entering the cell; here we just remove the mine


def end_player_turn(state: BattleState) -> None:
    """Apply end-of-turn effects, then trigger AI turn."""
    _apply_fire_damage(state)
    _apply_port_repairs(state)
    state.phase = "ai"


def _apply_fire_damage(state: BattleState) -> None:
    for ship in state.player_admiral.armada.ships + state.ai_admiral.armada.ships:
        if ship.state == ShipState.Sunk:
            continue
        for pos in ship.occupied_cells():
            cell = state.battlefield.cells.get((pos.x, pos.y))
            if cell and CellEffectType.Fire in cell.effects:
                bridge = ship.cells[0]
                bridge.hp = max(0, bridge.hp - 1)
                if bridge.hp == 0 and ship.state == ShipState.Alive:
                    ship.state = ShipState.Dying
                    ship.dying_turns_left = 2


def _apply_port_repairs(state: BattleState) -> None:
    for ship in state.player_admiral.armada.ships:
        if ship.state == ShipState.Sunk:
            continue
        for pos in ship.occupied_cells():
            neighbors = [(pos.x+1,pos.y),(pos.x-1,pos.y),(pos.x,pos.y+1),(pos.x,pos.y-1)]
            for nx, ny in neighbors:
                nc = state.battlefield.cells.get((nx, ny))
                if nc and nc.obj == CellObjectType.Port:
                    for c in ship.cells:
                        if c.hp < c.hp_max:
                            c.hp = min(c.hp_max, c.hp + 1)


def check_victory(state: BattleState) -> str | None:
    player_alive = any(s.state != ShipState.Sunk for s in state.player_admiral.armada.ships)
    ai_alive = any(s.state != ShipState.Sunk for s in state.ai_admiral.armada.ships)
    if not ai_alive:
        return "player"
    if not player_alive:
        return "ai"
    return None
