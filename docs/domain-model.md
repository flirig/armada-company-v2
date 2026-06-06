# Domain model

All entities live in `armada/domain/` as Python dataclasses. No ORM, no I/O.

## Enums (`enums.py`)

```python
class CellType(Enum):
    Bridge = "bridge"
    Weapon = "weapon"
    Armor  = "armor"
    Supply = "supply"
    Hull   = "hull"

class ModuleType(Enum):
    Torpedo         = "torpedo"
    BallisticMissile = "ballistic_missile"
    Mortar          = "mortar"
    Bomber          = "bomber"
    AaGun           = "aa_gun"

class Direction(Enum):
    North = "N"
    East  = "E"
    South = "S"
    West  = "W"

class ShipState(Enum):
    Alive  = "alive"
    Dying  = "dying"   # bridge destroyed, 2 turns left
    Sunk   = "sunk"

class TerrainHeight(Enum):
    DeepSea      = 0
    ShallowWater = 1
    Land         = 2
    Mountain     = 3

class CellObjectType(Enum):
    Port    = "port"
    OilRig  = "oil_rig"
    Mine    = "mine"
    NpcShip = "npc_ship"

class CellEffectType(Enum):
    Ice   = "ice"
    Storm = "storm"
    Fog   = "fog"
    Fire  = "fire"

class MarkerType(Enum):
    Hit             = "hit"
    Miss            = "miss"
    AmmoLoss        = "ammo_loss"
    ObjectDetection = "object_detection"
    EffectTrace     = "effect_trace"
```

## Core dataclasses (`models.py`)

```python
@dataclass
class GridPos:
    x: int
    y: int

@dataclass
class ShipCell:
    cell_type: CellType
    module_type: ModuleType | None
    hp: int
    fired_this_turn: bool = False   # module activation lock

@dataclass
class Ship:
    cells: list[ShipCell]           # index 0 = bridge
    bridge_pos: GridPos             # bridge cell grid position
    facing: Direction
    state: ShipState = ShipState.Alive
    dying_turns_left: int = 0
    moved_this_turn: bool = False

    def occupied_cells(self) -> list[GridPos]:
        """Returns grid positions for all cells, bridge first, extending backward."""
        ...

    def draft(self) -> int:
        """1 light / 2 medium / 3 heavy based on cell count."""
        ...

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

@dataclass
class Admiral:
    name: str
    profile: str          # "mobile" | "offensive" | "heavy" | "recon" | "balanced"
    stats: AdmiralStats
    armada: Armada

@dataclass
class TurnBudget:
    fuel: int
    supply: int

    def spend_fuel(self, amount: int) -> bool: ...
    def spend_supply(self) -> bool: ...

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
    cells: dict[tuple[int,int], BattleGridCell]

@dataclass
class BattleState:
    battlefield: Battlefield
    player_admiral: Admiral
    ai_admiral: Admiral
    turn_budget: TurnBudget
    turn_number: int = 1
    phase: str = "player"    # "player" | "ai" | "victory" | "defeat"
```

## Cell HP table

| Cell type  | HP |
|------------|----|
| Armor      | 4  |
| Bridge     | 3  |
| Weapon     | 2  |
| Supply     | 2  |
| Plain hull | 2  |

Armor cells reduce incoming damage by 1 (minimum 1 applied).

## Ship visual keys (frontend)

Sprite keys used by `game.js` canvas renderer:

| Key | Cell type |
|---|---|
| `module_torpedo`          | Weapon / Torpedo |
| `module_ballistic_missile`| Weapon / BallisticMissile |
| `module_mortar`           | Weapon / Mortar |
| `module_bomber`           | Weapon / Bomber |
| `module_aa_gun`           | Weapon / AaGun |
| `module_bridge`           | Bridge |
| `module_armor`            | Armor |
| `module_supply`           | Supply |
| `module_engine`           | Hull |

Each key has `_damaged_light` (HP ≤ 66%) and `_damaged_heavy` (HP ≤ 33%) variants.
Sprites are 64×64 PNGs stored in `static/sprites/modules/`.
