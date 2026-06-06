from __future__ import annotations
from dataclasses import dataclass
from armada.domain.enums import ModuleType, Direction, CellEffectType, ShipState, CellType, TerrainHeight
from armada.domain.models import GridPos, Battlefield, Ship, _facing_delta


@dataclass
class ImpactResult:
    pos: GridPos
    damage: int
    effect: CellEffectType | None = None


def _ortho_neighbors(pos: GridPos) -> list[GridPos]:
    return [
        GridPos(pos.x + 1, pos.y),
        GridPos(pos.x - 1, pos.y),
        GridPos(pos.x, pos.y + 1),
        GridPos(pos.x, pos.y - 1),
    ]


def _in_bounds(pos: GridPos, bf: Battlefield) -> bool:
    return 0 <= pos.x < bf.width and 0 <= pos.y < bf.height


def _is_solid_terrain(pos: GridPos, bf: Battlefield) -> bool:
    cell = bf.cells.get((pos.x, pos.y))
    if cell is None:
        return True
    return cell.height in (TerrainHeight.Land, TerrainHeight.Mountain)


def _ship_at(pos: GridPos, all_ships: list[Ship]) -> bool:
    for ship in all_ships:
        if ship.state == ShipState.Dead:
            continue
        for p in ship.occupied_cells():
            if p == pos:
                return True
    return False


def fire(
    module: ModuleType,
    origin: GridPos,
    facing: Direction,
    battlefield: Battlefield,
    all_ships: list[Ship],
    target: GridPos | None = None,
) -> list[ImpactResult]:
    if module == ModuleType.Torpedo:
        return _fire_torpedo(origin, facing, battlefield, all_ships)
    if module == ModuleType.Mortar:
        return _fire_mortar(origin, facing, battlefield)
    if module == ModuleType.Bomber:
        return _fire_bomber(origin, facing, battlefield)
    if module == ModuleType.BallisticMissile:
        assert target is not None
        return _fire_ballistic(target, battlefield)
    if module == ModuleType.AaGun:
        return _fire_aa_gun(origin, facing, battlefield)
    return []


def _fire_torpedo(origin: GridPos, facing: Direction, bf: Battlefield,
                  all_ships: list[Ship]) -> list[ImpactResult]:
    dx, dy = _facing_delta(facing)
    x, y = origin.x + dx, origin.y + dy
    for _ in range(20):
        pos = GridPos(x, y)
        if not _in_bounds(pos, bf):
            break
        if _is_solid_terrain(pos, bf):
            break
        result = ImpactResult(pos=pos, damage=2)
        if _ship_at(pos, all_ships):
            return [result]  # stops on first ship hit
        x += dx
        y += dy
    return []


def _fire_mortar(origin: GridPos, facing: Direction, bf: Battlefield) -> list[ImpactResult]:
    dx, dy = _facing_delta(facing)
    impact = GridPos(origin.x + dx * 8, origin.y + dy * 8)
    results = []
    if _in_bounds(impact, bf):
        results.append(ImpactResult(pos=impact, damage=2))
        for n in _ortho_neighbors(impact):
            if _in_bounds(n, bf):
                results.append(ImpactResult(pos=n, damage=1))
    return results


def _fire_bomber(origin: GridPos, facing: Direction, bf: Battlefield) -> list[ImpactResult]:
    dx, dy = _facing_delta(facing)
    results = []
    x, y = origin.x + dx, origin.y + dy
    for _ in range(6):
        pos = GridPos(x, y)
        if not _in_bounds(pos, bf):
            break
        results.append(ImpactResult(pos=pos, damage=2))
        x += dx
        y += dy
    return results


def _fire_ballistic(target: GridPos, bf: Battlefield) -> list[ImpactResult]:
    results = []
    if _in_bounds(target, bf):
        cell = bf.cells.get((target.x, target.y))
        # Does not fire on land/mountain
        if cell and cell.height in (TerrainHeight.Land, TerrainHeight.Mountain):
            return []
        results.append(ImpactResult(pos=target, damage=3))
        for n in _ortho_neighbors(target):
            if _in_bounds(n, bf):
                results.append(ImpactResult(pos=n, damage=1))
    return results


def _fire_aa_gun(origin: GridPos, facing: Direction, bf: Battlefield) -> list[ImpactResult]:
    dx, dy = _facing_delta(facing)
    forward  = GridPos(origin.x + dx,      origin.y + dy)
    diag1    = GridPos(origin.x + dx - dy, origin.y + dy + dx)
    diag2    = GridPos(origin.x + dx + dy, origin.y + dy - dx)
    results = []
    for pos in (forward, diag1, diag2):
        if _in_bounds(pos, bf):
            results.append(ImpactResult(pos=pos, damage=1))
    return results


def apply_aa_intercept(result: ImpactResult, all_ships: list[Ship]) -> ImpactResult:
    for ship in all_ships:
        if ship.state == ShipState.Dead:
            continue
        occupied = ship.occupied_cells()
        for i, cell in enumerate(ship.cells):
            if cell.cell_type != CellType.Weapon or cell.module_type != ModuleType.AaGun:
                continue
            if cell.hp <= 0:
                continue
            gun_pos = occupied[i]
            if _aa_covers(gun_pos, ship.facing, result.pos):
                result.damage = max(0, result.damage - 1)
    return result


def _aa_covers(gun_pos: GridPos, facing: Direction, target: GridPos) -> bool:
    dx, dy = _facing_delta(facing)
    forward = GridPos(gun_pos.x + dx,      gun_pos.y + dy)
    diag1   = GridPos(gun_pos.x + dx - dy, gun_pos.y + dy + dx)
    diag2   = GridPos(gun_pos.x + dx + dy, gun_pos.y + dy - dx)
    return target in (forward, diag1, diag2)
