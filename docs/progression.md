# Progression

## After battle rewards

The player may receive one of:
- A new ship (added to armada if deck budget allows).
- A module (replace a weapon cell on an existing ship).
- A cell upgrade (increase HP or add armor to a cell).
- An admiral upgrade (increase one parameter by 1).
- Repair (restore HP of all damaged cells).
- An event (narrative choice with mechanical consequence).

## Run map nodes

| Node | Description |
|---|---|
| Battle      | Standard AI opponent |
| Elite battle| Harder AI, better reward |
| Shop        | Spend earned credits on upgrades |
| Repair      | Free HP restoration |
| Event       | Random narrative choice |
| Reward      | Free loot pick |
| Boss        | Final node, win condition |

## Progression vectors

- Upgrading admiral parameters (Fuel / Supply / Decks).
- Expanding deck capacity.
- Gaining new abilities.
- Rebuilding the armada (swap ships).
- Adding new ships.
- Replacing cells and modules on existing ships.

## Database persistence

Run progress is stored in the `run_progress` table via SQLAlchemy:

```python
class RunProgress(Base):
    __tablename__ = "run_progress"

    id: Mapped[str]          # session_id UUID
    admiral_data: Mapped[str]  # JSON serialized Admiral
    map_node: Mapped[int]
    credits: Mapped[int]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

Between-battle state is checkpointed after each reward screen. On reconnect, client `GET /run/{session_id}` restores from DB.
