# Combat rules

## Player turn

At the start of each turn `BattleState` refills `TurnBudget`:
- fuel = `admiral.stats.fuel_per_turn`
- supply = `admiral.stats.supply_per_turn`

Decks are not consumed in battle — they only constrain armada composition before battle.

## Movement

- Moving 1 cell costs **1 fuel per ship cell** (a 3-cell ship costs 3 fuel per step).
- A ship **cannot move after firing** in the same turn (`Ship.moved_this_turn` is checked before allowing fire, `Ship.fired_this_turn` is checked before allowing movement).

## Rotation

Rotation requires 1 forward step along the current heading, then the ship changes orientation. Rotation is performed around the bridge cell.

Example:
- 3-cell ship, bridge at rear, facing East.
- Takes 1 step forward (costs fuel).
- Rotates to face North — bridge stays in place, other cells reposition.

## Collisions and maneuver blocking

Ships do not deal collision damage. A maneuver is **invalid** if the ship's final position after movement or rotation overlaps any other ship's occupied cells.

**Validation is final-position only** — intermediate cells during movement are not checked.

Implementation: `MovementValidator.is_valid_move(ship, delta, all_ships, battlefield)` and `MovementValidator.is_valid_rotation(ship, new_facing, all_ships, battlefield)` both return `bool`.

## Draft and terrain

| Draft | Deep sea | Shallow water | Land | Mountain |
|-------|----------|---------------|------|----------|
| 1 — light  | ✓ | ✓ | ✗ | ✗ |
| 2 — medium | ✓ | ✗ | ✗ | ✗ |
| 3 — heavy  | ✓ | ✗ | ✗ | ✗ |

No ship can enter Land or Mountain cells.

## AA defense

Works automatically when an incoming projectile passes through the AA gun's coverage arc.

Coverage: **3-cell forward arc** centered on the gun cell — the cell directly ahead plus the two diagonally-adjacent forward cells. Arc rotates with the ship.

Intercepted projectile: incoming damage reduced by 1 (minimum 0). Checked for each undestroyed AA gun cell whose arc covers the impact cell.

## Action limits

- Each module can be activated **at most once per turn**.
- Activating a module costs **1 supply**.
- A ship that has fired **cannot move** later in the same turn.

## Bridge destruction

When a Bridge cell reaches 0 HP:
- `Ship.state` → `ShipState.Dying`
- `Ship.dying_turns_left` = 2
- Ship can still fire for those 2 turns but **cannot move**.
- After 2 turns the ship is removed from the battlefield (`ShipState.Sunk`).
