from __future__ import annotations
from armada.domain.enums import Direction, TerrainHeight, ShipState
from armada.domain.models import Ship, GridPos, Battlefield, _facing_delta
from armada.domain.factories import (
    FIELD_WIDTH, FIELD_HEIGHT,
    PLAYER_Y_MIN, PLAYER_Y_MAX,
    AI_Y_MIN, AI_Y_MAX,
)


def _rotate_cw(d: Direction) -> Direction:
    return {Direction.North: Direction.East, Direction.East: Direction.South,
            Direction.South: Direction.West, Direction.West: Direction.North}[d]

def _rotate_ccw(d: Direction) -> Direction:
    return {Direction.North: Direction.West, Direction.West: Direction.South,
            Direction.South: Direction.East, Direction.East: Direction.North}[d]


def _in_bounds(pos: GridPos) -> bool:
    return 0 <= pos.x < FIELD_WIDTH and 0 <= pos.y < FIELD_HEIGHT


def _in_zone(pos: GridPos, is_player: bool) -> bool:
    if is_player:
        return PLAYER_Y_MIN <= pos.y <= PLAYER_Y_MAX
    return AI_Y_MIN <= pos.y <= AI_Y_MAX


class MovementValidator:

    @staticmethod
    def _occupied_set(ships: list[Ship], exclude: Ship) -> set[tuple[int, int]]:
        result = set()
        for s in ships:
            if s is exclude or s.state == ShipState.Dead:
                continue
            for p in s.occupied_cells():
                result.add((p.x, p.y))
        return result

    @staticmethod
    def _terrain_ok(pos: GridPos, draft: int, bf: Battlefield,
                    allow_one_shallow: bool = False, shallow_used: list | None = None) -> bool:
        cell = bf.cells.get((pos.x, pos.y))
        if cell is None:
            return False
        h = cell.height
        if h == TerrainHeight.Land or h == TerrainHeight.Mountain:
            return False
        if draft >= 2 and h == TerrainHeight.ShallowWater:
            if allow_one_shallow and shallow_used is not None and len(shallow_used) == 0:
                shallow_used.append(pos)
                return True
            return False
        return True

    @classmethod
    def is_valid_move(
        cls,
        ship: Ship,
        direction: Direction,
        all_ships: list[Ship],
        battlefield: Battlefield,
        is_player: bool = True,
    ) -> bool:
        if not ship.can_move:
            return False
        dx, dy = _facing_delta(direction)
        new_bridge = GridPos(ship.bridge_pos.x + dx, ship.bridge_pos.y + dy)
        occupied = cls._occupied_set(all_ships, ship)
        draft = ship.draft()
        bx, by = -dx, -dy
        new_positions = [GridPos(new_bridge.x + bx * i, new_bridge.y + by * i)
                         for i in range(len(ship.cells))]
        for p in new_positions:
            if not _in_bounds(p):
                return False
            if not _in_zone(p, is_player):
                return False
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
        is_player: bool = True,
    ) -> bool:
        if not ship.can_move:
            return False
        new_facing = _rotate_cw(ship.facing) if clockwise else _rotate_ccw(ship.facing)
        dx, dy = _facing_delta(ship.facing)
        new_bridge = GridPos(ship.bridge_pos.x + dx, ship.bridge_pos.y + dy)
        bx2, by2 = -_facing_delta(new_facing)[0], -_facing_delta(new_facing)[1]
        new_positions = [GridPos(new_bridge.x + bx2 * i, new_bridge.y + by2 * i)
                         for i in range(len(ship.cells))]
        occupied = cls._occupied_set(all_ships, ship)
        draft = ship.draft()
        # allow one shallow cell as pivot point during rotation
        shallow_used: list = []
        for p in new_positions:
            if not _in_bounds(p):
                return False
            if not _in_zone(p, is_player):
                return False
            if (p.x, p.y) in occupied:
                return False
            if not cls._terrain_ok(p, draft, battlefield,
                                    allow_one_shallow=True, shallow_used=shallow_used):
                return False
        return True

    @classmethod
    def apply_rotation(cls, ship: Ship, clockwise: bool) -> None:
        dx, dy = _facing_delta(ship.facing)
        ship.bridge_pos = GridPos(ship.bridge_pos.x + dx, ship.bridge_pos.y + dy)
        ship.facing = _rotate_cw(ship.facing) if clockwise else _rotate_ccw(ship.facing)
        ship.moved_this_turn = True
