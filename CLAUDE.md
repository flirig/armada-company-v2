# Armada Company v2 - Development Notes

## UI/UX - Current Implementation

### Layout Architecture
- **Vertical mobile-first layout** used for all screen sizes
- **No sidebar** - all content arranged vertically
- Game board **never requires scrolling** - entire field visible at once

### UI Components

#### Top Bar (mobile-top-bar)
- Fixed height, centered
- Shows: Turn number, fuel (⛽), supply (📦), End Turn button
- Always visible at top

#### Game Board (canvas)
- Dimensions: 540x1152 pixels (logical size)
- **Scales dynamically** to fit between top bar and module panel
- **Maintains aspect ratio** - always shows full battlefield
- Centered horizontally and vertically in available space
- No scrolling, no overflow

#### Module HUD Panel (mobile-ship-panel)
- **Always visible** - never hidden
- Fixed minimum height: 120px (prevents field size jumping)
- Shows ship modules as interactive buttons when ship selected
- Shows "Select a ship" when no ship is selected
- Centered content

### Module Selection Behavior

#### When Ship is Selected
1. Shows ship name and state badge
2. Displays all modules as clickable buttons
3. Each module button shows:
   - Module label (MRT, BRI, AAG, ARM, etc.)
   - Type (weapon, bridge, armor, supply, hull)
   - HP (health points)

#### Module Button Styling
- Size: 56x60 pixels
- Smaller font sizes for compact layout (fits more modules per line)
- Color-coded by type:
  - Bridge: Blue border (#4a7aff)
  - Weapon: Orange border (#ff8844)
  - Armor: Gray-blue border (#6688aa)
  - Supply: Green border (#44aa66)
  - Hull: Dark gray border (#445566)
- **Active state**: Glowing blue border with box-shadow effect

#### Module Activation

**Bridge Module** (type='bridge')
- Activates movement mode
- Shows reachable cells highlighted in green
- Player clicks green cell to move
- Click bridge again to cancel movement
- Cannot move if ship already moved this turn

**Weapon Modules** (type='weapon')
- Activates firing/targeting
- Different weapons have different behaviors:
  - **Ballistic Missile**: Enters targeting mode, shows range (10 cells), wait for target click
  - **Mortar, AA Gun, Torpedo**: Fire in direction ship is facing, immediate execution
- Cannot fire if:
  - Module already fired this turn
  - No supply available (supply=0)
  - Module destroyed (hp=0)
- Click weapon module again to cancel active targeting mode

**Other Modules** (armor, supply, hull)
- Currently display-only (no interaction)
- Show status information only

### Canvas Resizing Logic

The `resizeCanvas()` function:
1. Calculates available height: `window.innerHeight - topBar.height - shipPanel.height - 8px`
2. Calculates available width: `window.innerWidth - 8px`
3. Scales canvas to fit within available space
4. Maintains 540:1152 aspect ratio
5. Centers canvas vertically in available space
6. Prevents any scrolling

### Code Changes Made

#### JavaScript (game.js)
- Added `activeModuleIndex` state variable
- Implemented `onModuleClick(shipIndex, cellIndex)` for module activation/deactivation
- Updated `renderMobileShipPanel()` to show modules with proper click handlers
- Fixed bridge detection: uses `cell.type === 'bridge'` instead of position check
- Updated `resizeCanvas()` for proper scaling without overflow
- Module panel always displays (never hidden)

#### CSS (index.html)
- Removed desktop media queries (vertical layout everywhere)
- Hidden sidebar completely (`display: none !important`)
- Set `game-area` overflow to `hidden` (prevents scrolling)
- Mobile top bar centered with `justify-content: center`
- Mobile ship panel: flex layout, centered, fixed min-height 120px
- Module buttons: smaller sizes (56x60px), wrapping grid layout
- Added active state styling with glowing effect

### Interaction Flow

1. **Start Game** → Empty HUD shows "Select a ship"
2. **Click Ship on Canvas** → Ship selected, HUD shows its modules
3. **Click Module in HUD** → Module activates:
   - Bridge → Movement mode (show green cells)
   - Weapon → Firing/targeting mode
4. **Click Again on Same Module** → Deactivate, cancel action
5. **Click Different Module** → Previous deactivates, new activates
6. **Click on Canvas** → Execute action (move/fire) or just select different ship

### Responsive Behavior

- **All screen sizes**: Use same vertical layout (mobile-first)
- **Canvas scaling**: Automatically fills available space between panels
- **Panel heights**: Fixed to prevent field jumping
- **Module buttons**: Wrap to multiple lines if needed
- **Text sizing**: Reduced for compact display

### Known Limitations & Notes

- Sidebar completely removed (never displayed)
- Movement range calculated via BFS algorithm in frontend
- Ballistic missiles show range overlay (10 cell radius)
- Module buttons disabled when:
  - Module destroyed (hp=0)
  - Module already fired this turn
  - No supply for weapons
  - Ship already moved (for bridge)
- Active module selection is visual feedback only - doesn't affect game logic

### Future Improvements

If further changes needed:
- Could add swipe gestures for mobile module selection
- Could add visual indicators for resource costs
- Could show estimated damage on hover for weapons
- Could add undo functionality for movements
