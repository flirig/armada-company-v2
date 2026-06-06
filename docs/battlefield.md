# Battlefield

## Size

MVP: **15×32** grid (portrait, mobile-friendly). Coordinates (0,0) top-left.

Player zone: y ≤ 14. Buffer (shallow water): y 15–16. AI zone: y ≥ 17.

## Height levels

| `TerrainHeight` | Ships allowed |
|---|---|
| `DeepSea` (0)      | All drafts |
| `ShallowWater` (1) | Draft 1 only |
| `Land` (2)         | None |
| `Mountain` (3)     | None |

## Objects (`CellObjectType`)

| Object | Effect |
|---|---|
| Port    | Repairs adjacent ships at turn end (1 HP per cell) |
| OilRig  | If destroyed: fire on 4 orthogonal neighbors, 1 turn |
| Mine    | Explodes on ship entry: orthogonal splash 2 dmg, mine removed |
| NpcShip | Obstacle, 2 HP, destroyable |

## Effects (`CellEffectType`)

| Effect | Impact |
|---|---|
| Ice   | Movement costs +1 fuel per cell |
| Storm | Weapon range −2 |
| Fog   | Enemy ships in fog cells hidden from player view |
| Fire  | Ship ending turn in fire cell takes 1 damage to bridge |

## Markers (previous-turn layer)

Markers are placed on enemy cells when player actions resolve. Cleared at the start of each new player turn.

| `MarkerType` | Placed when |
|---|---|
| Hit              | Weapon impact dealt damage |
| Miss             | Weapon fired but hit no ship |
| AmmoLoss         | Module used but ran out of supply |
| ObjectDetection  | Recon revealed an object |
| EffectTrace      | Effect was triggered |

## `BattleGridCell` structure

```python
@dataclass
class BattleGridCell:
    pos: GridPos
    height: TerrainHeight
    obj: CellObjectType | None = None
    effects: list[CellEffectType] = field(default_factory=list)
    markers: list[MarkerType] = field(default_factory=list)
```
