# Armada and ships

## Armada

An armada is the admiral's set of ships. Total cell count across all ships must not exceed the admiral's `deck_limit`. No separate cap on the number of ships.

## Ship

A ship is a list of `ShipCell` objects. Ship size = number of cells. Index 0 is always the Bridge cell.

## Cell types

| Type | HP | Notes |
|---|---|---|
| Bridge  | 3 | Mandatory. Rotation pivot. Destruction → Dying state. |
| Weapon  | 2 | Holds one `ModuleType`. Destroyed weapon → module disabled permanently. |
| Armor   | 4 | Reduces incoming damage by 1 (min 1 applied). |
| Supply  | 2 | — |
| Hull    | 2 | Plain structural cell. |

## Draft

| Draft value | Class | Can enter |
|---|---|---|
| 1 — light  | Small ships (corvette, destroyer) | Deep sea + shallow water |
| 2 — medium | Medium ships (cruiser, missile boat) | Deep sea only |
| 3 — heavy  | Large ships (battleship, carrier) | Deep sea only |

Draft is computed from cell count by default; overrides allowed per design.

## Ship factories (`factories.py`)

```python
def create_battleship() -> Ship: ...    # 5 cells, draft 3
def create_carrier() -> Ship: ...       # 5 cells, draft 3
def create_cruiser() -> Ship: ...       # 3 cells, draft 2
def create_destroyer() -> Ship: ...     # 3 cells, draft 1
def create_corvette() -> Ship: ...      # 2 cells, draft 1
def create_missile_boat() -> Ship: ...  # 3 cells, draft 2

def create_random_armada(deck_budget: int) -> Armada:
    """Greedy-fill from shuffled factory list until budget is exhausted."""
    ...
```

## Example ships

### Missile cruiser
- 3 cells: Bridge (middle), Weapon/Torpedo (rear), Weapon/BallisticMissile (front).
- Draft 2. Deck cost 3.

### Trawler
- 3 cells: Bridge (rear), Armor (middle), Weapon/Mortar (front).
- Draft 1. Deck cost 3.
