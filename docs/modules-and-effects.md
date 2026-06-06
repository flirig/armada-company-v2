# Modules and effects

## Base modules

| Module | Supply cost | Pattern |
|---|---|---|
| Torpedo         | 1 | Piercing line forward, up to 20 cells |
| Mortar          | 1 | 8 cells ahead + orthogonal splash (1 cell) |
| Bomber          | 1 | 6-cell line forward, 2 damage each cell |
| AA Gun          | passive | 3-cell forward arc, auto-intercept |
| Ballistic Missile | 1 | Target any cell within radius 10; shockwave left+right of trajectory |

## Activation rules

- Each module costs **1 supply** when activated.
- A module can be activated **no more than once per turn**.
- Activating any module on a ship marks that ship as having fired (`Ship.fired_this_turn = True`), blocking further movement.

## `ModuleSystem.fire()` signature

```python
@dataclass
class ImpactResult:
    pos: GridPos
    damage: int
    effect: CellEffectType | None = None

def fire(
    module: ModuleType,
    origin: GridPos,
    facing: Direction,
    battlefield: Battlefield,
    all_ships: list[Ship],
    target: GridPos | None = None,   # required for BallisticMissile
) -> list[ImpactResult]:
    ...
```

`origin` is always the weapon cell's own grid position, not the bridge.

## AA intercept (passive)

After `fire()` produces `ImpactResult` list, each result is passed through `apply_aa_intercept(result, all_ships)` which reduces `result.damage` by 1 for each undestroyed AA gun whose forward arc covers `result.pos`.

## Effect spread

| Source | Spread pattern |
|---|---|
| Default weapon impact | Orthogonal 4-cell spread from impact cell, 1 step |
| Missile shockwave | 1 cell left + 1 cell right of missile trajectory |
| Oil rig destruction | Fire effect on all 4 orthogonal neighbors, 1 turn |
| Environmental (ice, storm, fog) | Static — placed at scenario setup, do not spread in MVP |

## Map object interactions

- **Port**: ship ending its turn adjacent to a port is repaired (1 HP to each damaged cell).
- **Oil rig**: if destroyed, sets adjacent cells to `CellEffectType.Fire` for 1 turn.
- **Mine**: ship entering the mine's cell triggers explosion — orthogonal splash damage 2, mine removed.
- **NPC ship**: treated as an obstacle; can be destroyed by weapons (2 HP total).
