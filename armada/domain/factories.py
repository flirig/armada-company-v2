from __future__ import annotations
import random
from armada.domain.enums import (
    CellType, ModuleType, Direction, TerrainHeight, CellObjectType
)
from armada.domain.models import (
    Ship, ShipCell, Armada, GridPos, Battlefield, BattleGridCell, BattleState,
    Admiral, AdmiralStats, TurnBudget,
)

# ── Field constants ────────────────────────────────────────────────────────────
FIELD_WIDTH  = 15
FIELD_HEIGHT = 32
PLAYER_Y_MIN, PLAYER_Y_MAX = 0, 14
BUFFER_Y_MIN, BUFFER_Y_MAX = 15, 16
AI_Y_MIN,     AI_Y_MAX     = 17, 31
PLAYER_ANCHOR_Y = 7
AI_ANCHOR_Y     = 24
AI_RNG_SEED     = 42


def _cell(ct: CellType, mt: ModuleType | None = None) -> ShipCell:
    hp = {CellType.Armor: 4, CellType.Bridge: 3, CellType.Weapon: 2,
          CellType.Supply: 2, CellType.Hull: 2}[ct]
    return ShipCell(cell_type=ct, module_type=mt, hp=hp, hp_max=hp)


# ── Ship factories (nose -> stern) ─────────────────────────────────────────────

def create_battleship() -> Ship:
    cells = [
        _cell(CellType.Weapon, ModuleType.Mortar),
        _cell(CellType.Bridge),
        _cell(CellType.Weapon, ModuleType.AaGun),
        _cell(CellType.Armor),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.South)


def create_carrier() -> Ship:
    cells = [
        _cell(CellType.Weapon, ModuleType.AaGun),
        _cell(CellType.Bridge),
        _cell(CellType.Supply),
        _cell(CellType.Weapon, ModuleType.Bomber),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.South)


def create_cruiser() -> Ship:
    cells = [
        _cell(CellType.Weapon, ModuleType.BallisticMissile),
        _cell(CellType.Bridge),
        _cell(CellType.Weapon, ModuleType.Torpedo),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.South)


def create_destroyer() -> Ship:
    cells = [
        _cell(CellType.Weapon, ModuleType.Mortar),
        _cell(CellType.Bridge),
        _cell(CellType.Weapon, ModuleType.Torpedo),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.South)


def create_corvette() -> Ship:
    cells = [
        _cell(CellType.Weapon, ModuleType.BallisticMissile),
        _cell(CellType.Bridge),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.South)


def create_missile_boat() -> Ship:
    cells = [
        _cell(CellType.Weapon, ModuleType.Torpedo),
        _cell(CellType.Bridge),
    ]
    return Ship(cells=cells, bridge_pos=GridPos(0, 0), facing=Direction.South)


_FACTORIES = [
    (create_battleship, 5),
    (create_carrier,    5),
    (create_cruiser,    3),
    (create_destroyer,  3),
    (create_corvette,   2),
    (create_missile_boat, 2),
]

# ── Admiral profiles ───────────────────────────────────────────────────────────

_ADMIRAL_PROFILES: dict[str, AdmiralStats] = {
    "standard":  AdmiralStats(fuel_per_turn=12, supply_per_turn=5,  deck_limit=13),
    "balanced":  AdmiralStats(fuel_per_turn=5,  supply_per_turn=5,  deck_limit=8),
    "mobile":    AdmiralStats(fuel_per_turn=8,  supply_per_turn=4,  deck_limit=6),
    "offensive": AdmiralStats(fuel_per_turn=3,  supply_per_turn=8,  deck_limit=7),
    "heavy":     AdmiralStats(fuel_per_turn=3,  supply_per_turn=4,  deck_limit=11),
    "recon":     AdmiralStats(fuel_per_turn=6,  supply_per_turn=4,  deck_limit=8, ability="recon_bonus"),
}


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


def create_admiral(profile: str, name: str, rng: random.Random | None = None) -> Admiral:
    stats = _ADMIRAL_PROFILES[profile]
    armada = create_random_armada(stats.deck_limit, rng)
    return Admiral(name=name, profile=profile, stats=stats, armada=armada)


# ── Procedural map generation ──────────────────────────────────────────────────

def _spawn_safe_zone(anchor_y: int) -> set[tuple[int, int]]:
    y0 = max(1, anchor_y - 4)
    y1 = min(FIELD_HEIGHT, anchor_y + 2)
    safe = set()
    for y in range(y0, y1 + 1):
        for x in range(FIELD_WIDTH):
            safe.add((x, y))
    return safe


def _generate_player_half(rng: random.Random, cells: dict[tuple[int, int], BattleGridCell]) -> None:
    safe = _spawn_safe_zone(PLAYER_ANCHOR_Y)

    # Coastline near top: 12% mountain, rest land, with openings
    for y in range(PLAYER_Y_MIN, PLAYER_Y_MIN + 3):
        for x in range(FIELD_WIDTH):
            if (x, y) in safe:
                continue
            cells[(x, y)].height = TerrainHeight.Mountain if rng.random() < 0.12 else TerrainHeight.Land
    # Opening in coastline: width 3-6 at random X
    opening_w = rng.randint(3, 6)
    opening_x = rng.randint(0, FIELD_WIDTH - opening_w)
    for y in range(PLAYER_Y_MIN, PLAYER_Y_MIN + 3):
        for x in range(opening_x, opening_x + opening_w):
            cells[(x, y)].height = TerrainHeight.DeepSea
    # Shallow water near coast
    for x in range(FIELD_WIDTH):
        if cells[(x, PLAYER_Y_MIN + 2)].height == TerrainHeight.Land or cells[(x, PLAYER_Y_MIN + 2)].height == TerrainHeight.Mountain:
            if (x, PLAYER_Y_MIN + 3) in cells and (x, PLAYER_Y_MIN + 3) not in safe:
                cells[(x, PLAYER_Y_MIN + 3)].height = TerrainHeight.ShallowWater

    # Island: 1-3 land cells
    island_cx = rng.randint(2, FIELD_WIDTH - 3)
    island_cy = rng.randint(5, 12)
    island_size = rng.randint(1, 3)
    island_cells: list[tuple[int, int]] = [(island_cx, island_cy)]
    for _ in range(island_size - 1):
        base = rng.choice(island_cells)
        dirs = [(1,0),(-1,0),(0,1),(0,-1)]
        rng.shuffle(dirs)
        for dx, dy in dirs:
            nc = (base[0]+dx, base[1]+dy)
            if nc not in island_cells and 0 <= nc[0] < FIELD_WIDTH and PLAYER_Y_MIN <= nc[1] <= PLAYER_Y_MAX and nc not in safe:
                island_cells.append(nc)
                break
    for ic in island_cells:
        if ic not in safe:
            cells[ic].height = TerrainHeight.Mountain if rng.random() < 0.35 else TerrainHeight.Land
            # Surround with shallow water
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nc = (ic[0]+dx, ic[1]+dy)
                if nc in cells and nc not in safe and cells[nc].height == TerrainHeight.DeepSea:
                    cells[nc].height = TerrainHeight.ShallowWater

    # Reefs: 1-2, BFS expansion 2-5 cells
    num_reefs = rng.randint(1, 2)
    for _ in range(num_reefs):
        rx = rng.randint(0, FIELD_WIDTH - 1)
        ry = rng.randint(PLAYER_Y_MIN + 1, PLAYER_Y_MAX - 2)
        if (rx, ry) in safe or cells[(rx, ry)].height != TerrainHeight.DeepSea:
            continue
        reef = [(rx, ry)]
        cells[(rx, ry)].height = TerrainHeight.ShallowWater
        expand = rng.randint(2, 5)
        for _ in range(expand):
            if not reef:
                break
            base = rng.choice(reef)
            dirs = [(1,0),(-1,0),(0,1),(0,-1)]
            rng.shuffle(dirs)
            for dx, dy in dirs:
                nc = (base[0]+dx, base[1]+dy)
                if nc in cells and nc not in safe and cells[nc].height == TerrainHeight.DeepSea and rng.random() < 0.55:
                    cells[nc].height = TerrainHeight.ShallowWater
                    reef.append(nc)
                    break

    # Port
    port_x = rng.randint(0, FIELD_WIDTH - 1)
    port_y = rng.randint(PLAYER_Y_MIN + 2, PLAYER_Y_MAX - 2)
    if cells[(port_x, port_y)].height == TerrainHeight.DeepSea:
        cells[(port_x, port_y)].obj = CellObjectType.Port

    # OilRig (70% chance)
    if rng.random() < 0.70:
        for _ in range(20):
            ox = rng.randint(0, FIELD_WIDTH - 1)
            oy = rng.randint(PLAYER_Y_MIN + 1, PLAYER_Y_MAX - 1)
            if cells[(ox, oy)].height == TerrainHeight.DeepSea and cells[(ox, oy)].obj is None and (ox, oy) not in safe:
                cells[(ox, oy)].obj = CellObjectType.OilRig
                break

    # Mine field: 3-6 mines near Y=2
    num_mines = rng.randint(3, 6)
    mine_y = 2
    placed = 0
    attempts = 0
    while placed < num_mines and attempts < 50:
        attempts += 1
        mx = rng.randint(0, FIELD_WIDTH - 1)
        if cells[(mx, mine_y)].height == TerrainHeight.DeepSea and cells[(mx, mine_y)].obj is None:
            cells[(mx, mine_y)].obj = CellObjectType.Mine
            placed += 1


def _mirror_to_ai_half(cells: dict[tuple[int, int], BattleGridCell]) -> None:
    """Mirror player half (Y=0-14) to AI half (Y=17-31) with Y inversion.

    Player Y=14 (nearest buffer) <-> AI Y=17 (nearest buffer).
    Formula: ai_y = 31 - y  (y=0->31, y=14->17).
    """
    for y in range(PLAYER_Y_MIN, PLAYER_Y_MAX + 1):
        ai_y = PLAYER_Y_MAX + AI_Y_MIN - y  # = 31 - y
        if ai_y < AI_Y_MIN or ai_y > AI_Y_MAX:
            continue
        for x in range(FIELD_WIDTH):
            src_cell = cells.get((x, y))
            dst_cell = cells.get((x, ai_y))
            if src_cell is None or dst_cell is None:
                continue
            dst_cell.height = src_cell.height
            if src_cell.obj == CellObjectType.Port:
                dst_cell.obj = CellObjectType.Port
            elif src_cell.obj == CellObjectType.OilRig:
                dst_cell.obj = CellObjectType.OilRig
            elif src_cell.obj == CellObjectType.Mine:
                dst_cell.obj = CellObjectType.Mine


def create_battlefield(width: int = FIELD_WIDTH, height: int = FIELD_HEIGHT,
                       rng: random.Random | None = None) -> Battlefield:
    rng = rng or random.Random(AI_RNG_SEED)
    cells: dict[tuple[int, int], BattleGridCell] = {}

    # Initialize all cells
    for y in range(height):
        for x in range(width):
            if BUFFER_Y_MIN <= y <= BUFFER_Y_MAX:
                h = TerrainHeight.ShallowWater
            else:
                h = TerrainHeight.DeepSea
            cells[(x, y)] = BattleGridCell(pos=GridPos(x, y), height=h)

    # Generate player half procedurally
    _generate_player_half(rng, cells)

    # Mirror to AI half
    _mirror_to_ai_half(cells)

    return Battlefield(width=width, height=height, cells=cells)


def _find_passable_x(cells: dict[tuple[int, int], BattleGridCell],
                     target_x: int, y: int, draft: int) -> int | None:
    """Find nearest passable x to target_x at given y."""
    for delta in range(FIELD_WIDTH):
        for dx in ([0, -delta, delta] if delta == 0 else [-delta, delta]):
            x = target_x + dx
            if 0 <= x < FIELD_WIDTH:
                cell = cells.get((x, y))
                if cell is None:
                    continue
                h = cell.height
                if h == TerrainHeight.Land or h == TerrainHeight.Mountain:
                    continue
                if draft >= 2 and h == TerrainHeight.ShallowWater:
                    continue
                if cell.obj is not None:
                    continue
                return x
    return None


def _place_ships(ships: list[Ship], cells: dict[tuple[int, int], BattleGridCell],
                 anchor_y: int, facing: Direction) -> None:
    count = len(ships)
    if count == 0:
        return
    step = max(2, (FIELD_WIDTH - 1) // count)
    for i, ship in enumerate(ships):
        target_x = min(FIELD_WIDTH - 1, i * step + 1)
        px = _find_passable_x(cells, target_x, anchor_y, ship.draft())
        if px is None:
            px = target_x
        ship.bridge_pos = GridPos(px, anchor_y)
        ship.facing = facing


def create_battle_state(player_profile: str, seed: int | None = None) -> BattleState:
    rng = random.Random(seed)
    player = create_admiral(player_profile, "Player", rng)
    ai_rng = random.Random(AI_RNG_SEED)
    ai = create_admiral("balanced", "AI", ai_rng)

    map_rng = random.Random(rng.randint(0, 2**32))
    battlefield = create_battlefield(rng=map_rng)

    _place_ships(player.armada.ships, battlefield.cells, PLAYER_ANCHOR_Y, Direction.South)
    _place_ships(ai.armada.ships,     battlefield.cells, AI_ANCHOR_Y,     Direction.North)

    budget = TurnBudget(fuel=player.stats.fuel_per_turn, supply=player.stats.supply_per_turn)
    return BattleState(
        battlefield=battlefield,
        player_admiral=player,
        ai_admiral=ai,
        turn_budget=budget,
    )
