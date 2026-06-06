# Admirals

## Role

The admiral defines strategy through parameters, abilities, and armada composition.

## Core parameters

| Parameter | Effect |
|---|---|
| Fuel    | Total fuel available each turn for ship movement |
| Supply  | Total module activations available each turn |
| Decks   | Maximum total ship cells in the armada |

## Balance bar

Each admiral has 15 total balance points distributed among the three parameters.

Example (Balanced profile): Fuel 5 / Supply 5 / Decks 5.

## Admiral profiles

| Profile | Fuel | Supply | Decks | Notes |
|---|---|---|---|---|
| Mobile     | 8 | 4 | 3  | Fast repositioning |
| Offensive  | 4 | 8 | 3  | Many module activations |
| Heavy      | 3 | 4 | 8  | Large armadas |
| Recon      | 6 | 3 | 6  | Recon bonus ability |
| Balanced   | 5 | 5 | 5  | All-rounder |

## MVP abilities

- **Recon bonus**: +2 cells to fog-of-war reveal range.
- **Module bonus**: +1 damage to a specific module type.

## AdmiralStats dataclass

```python
@dataclass
class AdmiralStats:
    fuel_per_turn: int
    supply_per_turn: int
    deck_limit: int
    ability: str | None = None    # "recon_bonus" | "module_bonus:<ModuleType>"
```

## Custom admiral (post-MVP)

- Distribute 15 balance points freely among Fuel / Supply / Decks.
- Choose 1 starting ability.
- Assemble starting armada within deck limit.
