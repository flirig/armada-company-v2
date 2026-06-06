from __future__ import annotations
import random
from armada.domain.enums import (
    CellType, ModuleType, Direction, TerrainHeight, CellObjectType
)
from armada.domain.models import (
    Ship, ShipCell, Armada, GridPos, Battlefield, BattleGridCell, BattleState,
    Admiral, AdmiralStats, TurnBudget,
)


def _cell(ct: CellType, mt: ModuleType | None = None) -> ShipCell:
    hp = {CellType.Armor: 4, CellType.Bridge: 3, CellType.Weapon: 2,
          CellType.Supply: 2, CellType.Hull: 2}[ct]
    return ShipCell(cell_type=ct, module_type=mt, hp=hp, hp_max=hp)


def create_battleship() -> Ship:
    cells = [
        _cell(CellType.Bridge),
        _cell(CellType.Armor),
        _cell(CellType.Weapon, ModuleType.Torpedo),
        _cell(CellType.Weapon, ModuleType.Mortar),
        _cell(CellType.Hull),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.East)


def create_carrier() -> Ship:
    cells = [
        _cell(CellType.Bridge),
        _cell(CellType.Weapon, ModuleType.Bomber),
        _cell(CellType.Weapon, ModuleType.AaGun),
        _cell(CellType.Supply),
        _cell(CellType.Hull),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.East)


def create_cruiser() -> Ship:
    cells = [
        _cell(CellType.Bridge),
        _cell(CellType.Weapon, ModuleType.Torpedo),
        _cell(CellType.Weapon, ModuleType.BallisticMissile),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.East)


def create_destroyer() -> Ship:
    cells = [
        _cell(CellType.Bridge),
        _cell(CellType.Weapon, ModuleType.Torpedo),
        _cell(CellType.Hull),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.East)


def create_corvette() -> Ship:
    cells = [
        _cell(CellType.Bridge),
        _cell(CellType.Weapon, ModuleType.Mortar),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.East)


def create_missile_boat() -> Ship:
    cells = [
        _cell(CellType.Bridge),
        _cell(CellType.Weapon, ModuleType.BallisticMissile),
        _cell(CellType.Hull),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.East)


_FACTORIES = [
    (create_battleship, 5),
    (create_carrier, 5),
    (create_cruiser, 3),
    (create_destroyer, 3),
    (create_corvette, 2),
    (create_missile_boat, 3),
]


def create_random_armada(deck_budget: int, rng: random.Random | None = None) -> Armada:
    rng = rng or random.Random()
    shuffled = list(_FACTORIES)
    rng.shuffle(shuffled)
    ships: list[Ship] = []
    used = 0
    for factory, cost in shuffled:
        if used + cost <= deck_budget:
            ships.append(factory())
            used += cost
    return Armada(ships=ships, deck_used=used, deck_limit=deck_budget)


_ADMIRAL_PROFILES = {
    "mobile":    AdmiralStats(fuel_per_turn=8, supply_per_turn=4, deck_limit=3),
    "offensive": AdmiralStats(fuel_per_turn=4, supply_per_turn=8, deck_limit=3),
    "heavy":     AdmiralStats(fuel_per_turn=3, supply_per_turn=4, deck_limit=8),
    "recon":     AdmiralStats(fuel_per_turn=6, supply_per_turn=3, deck_limit=6, ability="recon_bonus"),
    "balanced":  AdmiralStats(fuel_per_turn=5, supply_per_turn=5, deck_limit=5),
}


def create_admiral(profile: str, name: str, rng: random.Random | None = None) -> Admiral:
    stats = _ADMIRAL_PROFILES[profile]
    armada = create_random_armada(stats.deck_limit, rng)
    return Admiral(name=name, profile=profile, stats=stats, armada=armada)


def create_battlefield(width: int = 32, height: int = 15) -> Battlefield:
    cells: dict[tuple[int, int], BattleGridCell] = {}
    for y in range(height):
        for x in range(width):
            if x in (15, 16):
                h = TerrainHeight.ShallowWater
            else:
                h = TerrainHeight.DeepSea
            cells[(x, y)] = BattleGridCell(pos=GridPos(x, y), height=h)
    # Add a port in player zone
    cells[(4, 7)].obj = CellObjectType.Port
    # Add oil rig in AI zone
    cells[(27, 7)].obj = CellObjectType.OilRig
    return Battlefield(width=width, height=height, cells=cells)


def _place_ships(ships: list[Ship], start_x: int, facing: Direction) -> None:
    for i, ship in enumerate(ships):
        ship.bridge_pos = GridPos(start_x, i * 2 + 2)
        ship.facing = facing


def create_battle_state(player_profile: str, seed: int | None = None) -> BattleState:
    rng = random.Random(seed)
    player = create_admiral(player_profile, "Player", rng)
    ai = create_admiral("balanced", "AI", rng)
    _place_ships(player.armada.ships, 5, Direction.East)
    _place_ships(ai.armada.ships, 26, Direction.West)
    battlefield = create_battlefield()
    budget = TurnBudget(fuel=player.stats.fuel_per_turn, supply=player.stats.supply_per_turn)
    return BattleState(
        battlefield=battlefield,
        player_admiral=player,
        ai_admiral=ai,
        turn_budget=budget,
    )
