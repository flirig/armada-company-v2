# User Interface & Interaction Design

## Layout Overview

The game uses a **vertical mobile-first layout** optimized for touch and small screens, applied uniformly across all device sizes.

```
┌──────────────────────────────────────┐
│  Top Bar (fixed)                     │
│  Turn #, Fuel ⛽, Supply 📦, End Turn│
├──────────────────────────────────────┤
│                                      │
│       Game Board (Canvas)            │
│       Scales to fit available space  │
│       540px × 1152px aspect ratio   │
│       No scrolling                   │
│                                      │
├──────────────────────────────────────┤
│  Module HUD Panel (fixed min 120px) │
│  "Select a ship" or Ship + Modules  │
└──────────────────────────────────────┘
```

## Component Specifications

### Top Bar (`#mobile-top-bar`)
- **Height**: Flexible (auto), typically ~40-50px
- **Position**: Fixed at top
- **Content**: Centered
  - Phase badge ("YOUR TURN" / "AI TURN")
  - Turn number
  - Fuel counter with ⛽ icon
  - Supply counter with 📦 icon
  - "End Turn" button (green, visible when player's turn)
- **Background**: Dark blue `#0d1f30`
- **Border**: Bottom border `2px solid #2a4a6a`

### Game Board (`#canvas`)
- **Logical size**: 540px wide × 1152px tall (16:32 grid)
- **Display size**: Scales dynamically to fill available space between top bar and module panel
- **Aspect ratio**: Always maintained (540:1152 = 15:32)
- **Scaling algorithm**:
  ```
  availableHeight = window.innerHeight - topBar.height - modulePanel.height - 8px
  availableWidth = window.innerWidth - 8px
  
  aspectRatio = 540 / 1152
  width = availableWidth
  height = width / aspectRatio
  
  if (height > availableHeight) {
    height = availableHeight
    width = height * aspectRatio
  }
  ```
- **Positioning**: Centered horizontally and vertically in available space
- **Overflow**: Hidden (no scrolling)
- **Rendering**: Pixel-art style with grid, terrain, ships, effects

### Module HUD Panel (`#mobile-ship-panel`)
- **Height**: Minimum 120px (always maintained to prevent field jumping)
- **Position**: Fixed at bottom
- **Content layout**: Flex column, centered
- **State 1 - No ship selected**:
  - Single centered text: "Select a ship"
- **State 2 - Ship selected**:
  - Header (centered):
    - Ship name/type (e.g., "Battleship", "Cruiser", "Missile Boat")
    - State badge (ACTIVE, DYING, DEAD)
  - Module grid:
    - Horizontal grid with wrapping
    - Gap: 8px between buttons
    - Center-aligned

## Module Buttons

### Visual Design
- **Size**: 56px wide × 60px tall (scaled down from original 62×72 for compact display)
- **Border**: 2px solid (color by type)
- **Border radius**: 6px
- **Padding**: 4px 3px (compact spacing)
- **Content**: 3 centered lines
  - Label (11px, bold) - e.g., "MRT", "BRI", "AAG"
  - Type (7px, small caps) - "weapon", "bridge", "armor", "supply", "hull"
  - HP (8px) - "2/2", "3/3", "✕ sunk" if destroyed

### Color Scheme by Module Type
| Type | Border Color | Background | Notes |
|------|-------------|-----------|-------|
| Bridge | `#4a7aff` (blue) | `#1a2a4a` | Movement control |
| Weapon | `#ff8844` (orange) | `#2a1a1a` | Firing/targeting |
| Armor | `#6688aa` (gray-blue) | `#1a1a2a` | Passive |
| Supply | `#44aa66` (green) | `#1a2a1a` | Passive |
| Hull | `#445566` (dark gray) | `#0a1a2a` | Passive |

### Button States

**Disabled States**:
- `cell-dead`: opacity 0.35, border `#333`
- `cell-fired`: bg `rgba(160, 80, 0, 0.35)`, cursor default
- `cell-no-supply`: opacity 0.5, cursor default

**Active State** (`active` class):
- Box-shadow: Glowing blue `0 0 12px rgba(100, 200, 255, 0.8), inset 0 0 6px rgba(100, 200, 255, 0.4)`
- Border color: `#4accff` (bright blue)
- Visual feedback: User knows which module is active

## Interaction Model

### Module Activation

**Bridge Module** (`cell.type === 'bridge'`)
1. Click bridge button → Activates movement mode
2. Canvas shows reachable cells highlighted in green (BFS from ship position)
3. Player clicks green cell → Ship moves to that cell
4. Click bridge button again → Cancels movement, returns to normal view
5. Disabled if: Ship already moved this turn

**Weapon Modules** (`cell.type === 'weapon'`)
1. Click weapon button → Activates firing mode
2. Behavior depends on weapon type:
   - **Ballistic Missile**: Shows range overlay (10 cells from ship), waits for target click on canvas
   - **Other weapons** (Mortar, AA Gun, Torpedo): Fires immediately in ship's facing direction
3. Click weapon button again → Cancels active targeting (for ballistic)
4. Disabled if:
   - Module destroyed (hp=0)
   - Already fired this turn
   - No supply available (supply=0)

**Other Modules** (Armor, Supply, Hull)
- Display-only (no interaction)
- Show status information

### User Flow

```
1. Game starts
   ↓
2. Module panel shows "Select a ship"
   ↓
3. Click ship on canvas
   ├─→ Ship highlighted with blue border
   ├─→ Module panel updates showing ship's modules
   ├─→ Status bar shows "Ship selected. Click modules in HUD to activate."
   ↓
4. Click module button
   ├─→ Module button glows blue (active state)
   ├─→ Mode activates (movement or firing)
   ├─→ Canvas updates (shows green cells or targeting overlay)
   ↓
5a. Movement mode: Click green cell
   ├─→ Ship moves
   ├─→ Module deactivates
   ├─→ Canvas returns to normal
   ↓
5b. Weapon mode: Click target or repeat click
   ├─→ Fire weapon (or cancel if ballistic)
   ├─→ Module deactivates
   ├─→ Canvas returns to normal
   ↓
6. End turn / Continue
```

## Responsive Behavior

### All Screen Sizes
- Same vertical layout (mobile-first applied universally)
- No sidebar at any breakpoint
- Canvas always scales to fit available space

### Canvas Scaling Examples
| Screen | Available Space | Canvas Display |
|--------|-----------------|-----------------|
| 540px (mobile) | ~400px wide | Fills most of width, shrinks height proportionally |
| 1024px (tablet) | ~800px wide | Larger display, maintains aspect ratio |
| 1920px (desktop) | ~1900px wide | Even larger, but no wider than 540px logical × calculated height |

### Touch & Click
- All buttons sized for touch (56×60px minimum)
- Canvas click/touch coordinates mapped to grid position via `(clientX - rect.left) * scaleX / CELL`
- No hover effects required (works on touch devices)

## CSS Architecture

Key classes:
- `#mobile-top-bar` - Top information bar
- `#game-area` - Container for canvas (flex: 1, overflow: hidden)
- `#mobile-ship-panel` - Bottom module HUD (min-height: 120px)
- `.mobile-cell-btn` - Individual module buttons
- `.mobile-cell-btn.active` - Glowing blue active state
- `.mobile-cell-btn.cell-dead`, `.cell-fired`, `.cell-no-supply` - Disabled states
- `.mcb-label`, `.mcb-type`, `.mcb-hp` - Button text layers

## JavaScript State

Key variables tracking UI state:
- `selectedShipIndex`: Which ship is currently selected (null if none)
- `activeModuleIndex`: Which module button is pressed (null if none)
- `actionMode`: Current interaction mode (MODE_NONE, MODE_MOVE_PATH, MODE_TARGETING_MISSILE)
- `validMoveCells`: Array of reachable positions for movement
- `pendingFireInfo`: Stores {shipIndex, cellIndex} during ballistic targeting

## Canvas Rendering

The canvas renders in this order:
1. **Terrain**: Grid cells with terrain colors (deep sea, shallow water, land, mountain)
2. **Objects**: Ports, oil rigs, mines, NPC ships
3. **Overlays**: Fire effects, movement paths, targeting ranges
4. **AI Ships**: Rendered without outlines (enemy fleet)
5. **Player Ships**: Rendered with selection highlight if active
6. **Markers**: Hit/miss indicators from previous shots
7. **Hover highlight**: Semi-transparent square on hovered cell

Selection highlight: Blue border around all occupied cells of selected ship.

## Performance Notes

- Canvas resize recalculated on window resize (debounced implicitly by requestAnimationFrame in render loop)
- Module panel rendering: Full refresh when ship selection changes or game state updates
- No virtual scrolling needed (field always visible, no long lists)
- Touch scrolling on mobile disabled for module panel (flex layout, overflow hidden)

## Accessibility Considerations

- High contrast colors for color-blind users
- Button sizes sufficient for touch
- Text labels always visible (not title-only)
- No flashing or rapid animations
- Module state clearly indicated (active = glowing)
