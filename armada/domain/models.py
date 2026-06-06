from __future__ import annotations
from dataclasses import dataclass, field
from armada.domain.enums import (
    CellType, ModuleType, Direction, ShipState,
    TerrainHeight, CellObjectType, CellEffectType, MarkerType,
)

@dataclass
class GridPos:
    x: int
    y: int

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GridPos):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))

@dataclass
class ShipCell:
    cell_type: CellType
    module_type: ModuleType | None
    hp: int
    hp_max: int
    fired_this_turn: bool = False

@dataclass
class Ship:
    cells: list[ShipCell]
    bridge_pos: GridPos
    facing: Direction
    state: ShipState = ShipState.Alive
    dying_turns_left: int = 0
    moved_this_turn: bool = False
    fired_this_turn: bool = False  # any cell fired

    def occupied_cells(self) -> list[GridPos]:
        """Bridge + cells extending backward from bridge based on facing."""
        dx, dy = _facing_delta(self.facing)
        # backward direction
        bx, by = -dx, -dy
        result = []
        for i, _ in enumerate(self.cells):
            result.append(GridPos(self.bridge_pos.x + bx * i, self.bridge_pos.y + by * i))
        return result

    def draft(self) -> int:
        n = len(self.cells)
        if n <= 2:
            return 1
        if n <= 3:
            return 2
        return 3

def _facing_delta(facing: Direction) -> tuple[int, int]:
    return {
        Direction.North: (0, -1),
        Direction.South: (0,  1),
        Direction.East:  (1,  0),
        Direction.West:  (-1, 0),
    }[facing]

@dataclass
class Armada:
    ships: list[Ship]
    deck_used: int
    deck_limit: int

@dataclass
class AdmiralStats:
    fuel_per_turn: int
    supply_per_turn: int
    deck_limit: int
    ability: str | None = None

@dataclass
class Admiral:
    name: str
    profile: str
    stats: AdmiralStats
    armada: Armada

@dataclass
class TurnBudget:
    fuel: int
    supply: int

    def spend_fuel(self, amount: int) -> bool:
        if self.fuel < amount:
            return False
        self.fuel -= amount
        return True

    def spend_supply(self) -> bool:
        if self.supply < 1:
            return False
        self.supply -= 1
        return True

@dataclass
class BattleGridCell:
    pos: GridPos
    height: TerrainHeight
    obj: CellObjectType | None = None
    effects: list[CellEffectType] = field(default_factory=list)
    markers: list[MarkerType] = field(default_factory=list)

@dataclass
class Battlefield:
    width: int
    height: int
    cells: dict[tuple[int, int], BattleGridCell]

@dataclass
class BattleState:
    battlefield: Battlefield
    player_admiral: Admiral
    ai_admiral: Admiral
    turn_budget: TurnBudget
    turn_number: int = 1
    phase: str = "player"
