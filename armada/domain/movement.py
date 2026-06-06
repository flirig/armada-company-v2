from __future__ import annotations
from armada.domain.enums import Direction, TerrainHeight, ShipState
from armada.domain.models import Ship, GridPos, Battlefield, _facing_delta


def _rotate_cw(d: Direction) -> Direction:
    return {Direction.North: Direction.East, Direction.East: Direction.South,
            Direction.South: Direction.West, Direction.West: Direction.North}[d]

def _rotate_ccw(d: Direction) -> Direction:
    return {Direction.North: Direction.West, Direction.West: Direction.South,
            Direction.South: Direction.East, Direction.East: Direction.North}[d]


class MovementValidator:

    @staticmethod
    def _occupied_set(ships: list[Ship], exclude: Ship) -> set[tuple[int, int]]:
        result = set()
        for s in ships:
            if s is exclude or s.state == ShipState.Sunk:
                continue
            for p in s.occupied_cells():
                result.add((p.x, p.y))
        return result

    @staticmethod
    def _terrain_ok(pos: GridPos, draft: int, bf: Battlefield) -> bool:
        cell = bf.cells.get((pos.x, pos.y))
        if cell is None:
            return False
        h = cell.height
        if h == TerrainHeight.Land or h == TerrainHeight.Mountain:
            return False
        if draft >= 2 and h == TerrainHeight.ShallowWater:
            return False
        return True

    @classmethod
    def is_valid_move(
        cls,
        ship: Ship,
        direction: Direction,
        all_ships: list[Ship],
        battlefield: Battlefield,
    ) -> bool:
        if ship.fired_this_turn or ship.state != ShipState.Alive:
            return False
        dx, dy = _facing_delta(direction)
        new_bridge = GridPos(ship.bridge_pos.x + dx, ship.bridge_pos.y + dy)
        occupied = cls._occupied_set(all_ships, ship)
        draft = ship.draft()
        # backward direction relative to movement direction
        bx, by = -dx, -dy
        # compute new occupied positions
        new_positions = []
        for i in range(len(ship.cells)):
            p = GridPos(new_bridge.x + bx * i, new_bridge.y + by * i)
            new_positions.append(p)
        for p in new_positions:
            if (p.x, p.y) in occupied:
                return False
            if not cls._terrain_ok(p, draft, battlefield):
                return False
        return True

    @classmethod
    def apply_move(cls, ship: Ship, direction: Direction) -> None:
        dx, dy = _facing_delta(direction)
        ship.bridge_pos = GridPos(ship.bridge_pos.x + dx, ship.bridge_pos.y + dy)
        ship.moved_this_turn = True

    @classmethod
    def is_valid_rotation(
        cls,
        ship: Ship,
        clockwise: bool,
        all_ships: list[Ship],
        battlefield: Battlefield,
    ) -> bool:
        if ship.fired_this_turn or ship.state != ShipState.Alive:
            return False
        new_facing = _rotate_cw(ship.facing) if clockwise else _rotate_ccw(ship.facing)
        # step forward first
        dx, dy = _facing_delta(ship.facing)
        new_bridge = GridPos(ship.bridge_pos.x + dx, ship.bridge_pos.y + dy)
        # compute new occupied with new_bridge + new_facing (backward cells)
        bx2, by2 = -_facing_delta(new_facing)[0], -_facing_delta(new_facing)[1]
        new_positions = [GridPos(new_bridge.x + bx2 * i, new_bridge.y + by2 * i)
                         for i in range(len(ship.cells))]
        occupied = cls._occupied_set(all_ships, ship)
        draft = ship.draft()
        for p in new_positions:
            if (p.x, p.y) in occupied:
                return False
            if not cls._terrain_ok(p, draft, battlefield):
                return False
        return True

    @classmethod
    def apply_rotation(cls, ship: Ship, clockwise: bool) -> None:
        dx, dy = _facing_delta(ship.facing)
        ship.bridge_pos = GridPos(ship.bridge_pos.x + dx, ship.bridge_pos.y + dy)
        ship.facing = _rotate_cw(ship.facing) if clockwise else _rotate_ccw(ship.facing)
        ship.moved_this_turn = True
