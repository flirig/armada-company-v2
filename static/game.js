// Armada Company v2 — game client
'use strict';

const GRID_WIDTH = 15;
const GRID_HEIGHT = 32;
const CELL = 40;
const CANVAS_WIDTH = GRID_WIDTH * CELL; // 600px
const CANVAS_HEIGHT = GRID_HEIGHT * CELL; // 1280px

const TERRAIN_COLORS = {
  0: '#1a3a5c', // DeepSea
  1: '#2d6a8a', // ShallowWater
  2: '#5a7a4a', // Land
  3: '#6a5a4a', // Mountain
};

const CELL_TYPE_COLORS = {
  bridge: '#4a7aff',
  weapon: '#ff8844',
  armor:  '#6688aa',
  supply: '#44aa66',
  hull:   '#445566',
};

const MODULE_LABELS = {
  torpedo:          'TRP',
  ballistic_missile:'BMS',
  mortar:           'MRT',
  bomber:           'BMB',
  aa_gun:           'AAG',
};

// State
let sessionId = null;
let gameState = null;
let selectedShipIndex = null;
let hoveredCell = null;
let canvas, ctx;

// ── Init ──────────────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', () => {
  canvas = document.getElementById('canvas');
  ctx = canvas.getContext('2d');

  canvas.addEventListener('mousemove', onCanvasMouseMove);
  canvas.addEventListener('click', onCanvasClick);

  document.getElementById('btn-move-n').addEventListener('click', () => sendMove('N'));
  document.getElementById('btn-move-s').addEventListener('click', () => sendMove('S'));
  document.getElementById('btn-move-w').addEventListener('click', () => sendMove('W'));
  document.getElementById('btn-move-e').addEventListener('click', () => sendMove('E'));
  document.getElementById('btn-rotate-cw').addEventListener('click', () => sendRotate(true));
  document.getElementById('btn-rotate-ccw').addEventListener('click', () => sendRotate(false));
  document.getElementById('btn-end-turn').addEventListener('click', sendEndTurn);
  document.getElementById('btn-new-game').addEventListener('click', startNewGame);

  document.addEventListener('keydown', onKeyDown);

  startNewGame();
});

// ── API helpers ───────────────────────────────────────────────────────────────

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function startNewGame() {
  hideVictory();
  setStatus('Starting new game...', 'info');
  selectedShipIndex = null;
  try {
    const data = await apiPost('/game/new', { admiral_profile: 'balanced' });
    sessionId = data.session_id;
    applyState(data.state);
    setStatus('Game started! Select a ship and act.', 'ok');
  } catch (e) {
    setStatus('Failed to connect to server: ' + e.message, 'err');
  }
}

async function sendAction(body) {
  if (!sessionId) return;
  try {
    const data = await apiPost(`/game/${sessionId}/action`, body);
    applyState(data.state);
    if (!data.ok && data.error) {
      setStatus('Action failed: ' + data.error, 'err');
    }
    return data;
  } catch (e) {
    setStatus('Error: ' + e.message, 'err');
  }
}

// ── Actions ───────────────────────────────────────────────────────────────────

async function sendMove(direction) {
  if (selectedShipIndex === null) { setStatus('Select a ship first.', 'err'); return; }
  const res = await sendAction({ type: 'move', ship_index: selectedShipIndex, direction });
  if (res && res.ok) setStatus(`Ship moved ${direction}.`, 'ok');
}

async function sendRotate(clockwise) {
  if (selectedShipIndex === null) { setStatus('Select a ship first.', 'err'); return; }
  const res = await sendAction({ type: 'rotate', ship_index: selectedShipIndex, clockwise });
  if (res && res.ok) setStatus(`Ship rotated ${clockwise ? 'CW' : 'CCW'}.`, 'ok');
}

async function sendFire(shipIndex, cellIndex) {
  const ship = gameState.player_ships[shipIndex];
  const cell = ship.cells[cellIndex];
  const body = { type: 'fire', ship_index: shipIndex, module_cell_index: cellIndex };

  // Ballistic missile needs a target — use hovered cell or prompt
  if (cell.module === 'ballistic_missile') {
    if (!hoveredCell) {
      setStatus('Hover over a target cell on the grid, then click Fire.', 'info');
      // store pending fire for click
      pendingFire = { shipIndex, cellIndex };
      setStatus('Click target cell for Ballistic Missile.', 'info');
      return;
    }
    body.target = { x: hoveredCell.x, y: hoveredCell.y };
  }

  const res = await sendAction(body);
  if (res && res.ok) setStatus(`Fired ${cell.module || cell.type}!`, 'ok');
  else if (res) setStatus('Fire failed: ' + res.error, 'err');
}

let pendingFire = null;

async function sendEndTurn() {
  setStatus('Ending turn...', 'info');
  const res = await sendAction({ type: 'end_turn' });
  if (res && res.ok) setStatus('AI turn complete. Your move!', 'ok');
}

// ── State application ─────────────────────────────────────────────────────────

function applyState(state) {
  gameState = state;
  updateSidebar();
  renderCanvas();
  if (state.victory) showVictory(state.victory);
}

function updateSidebar() {
  if (!gameState) return;
  document.getElementById('turn-number').textContent = gameState.turn_number;
  document.getElementById('admiral-profile').textContent = 'balanced';

  const fuel = gameState.budget.fuel;
  const supply = gameState.budget.supply;
  // Estimate max from first player ship fuel_per_turn — use static 5 as balanced default
  const fuelMax = 5;
  const supplyMax = 5;

  document.getElementById('fuel-val').textContent = `${fuel} / ${fuelMax}`;
  document.getElementById('supply-val').textContent = `${supply} / ${supplyMax}`;
  document.getElementById('fuel-bar').style.width = `${Math.min(100, (fuel / fuelMax) * 100)}%`;
  document.getElementById('supply-bar').style.width = `${Math.min(100, (supply / supplyMax) * 100)}%`;

  const phase = gameState.phase;
  const phaseEl = document.getElementById('turn-phase');
  phaseEl.textContent = phase === 'player' ? 'Your Turn' : 'AI Turn';
  phaseEl.style.background = phase === 'player' ? '#1a3a5a' : '#3a1a1a';
  phaseEl.style.color = phase === 'player' ? '#6aaaff' : '#ff6a6a';

  renderShipList();
}

function renderShipList() {
  const list = document.getElementById('ship-list');
  list.innerHTML = '';

  gameState.player_ships.forEach((ship, idx) => {
    const card = document.createElement('div');
    card.className = 'ship-card' +
      (ship.state === 'sunk' ? ' sunk' : '') +
      (ship.state === 'dying' ? ' dying' : '') +
      (selectedShipIndex === idx ? ' selected' : '');

    // Header
    const header = document.createElement('div');
    header.className = 'ship-card-header';

    const nameEl = document.createElement('span');
    nameEl.className = 'ship-name';
    nameEl.textContent = shipTypeName(ship);

    const stateEl = document.createElement('span');
    stateEl.className = `ship-state state-${ship.state}`;
    stateEl.textContent = ship.state.toUpperCase();

    header.appendChild(nameEl);
    header.appendChild(stateEl);
    card.appendChild(header);

    // Cells
    const cellsEl = document.createElement('div');
    cellsEl.className = 'ship-cells';
    ship.cells.forEach(cell => {
      const badge = document.createElement('span');
      badge.className = `cell-badge cell-${cell.type}` + (cell.hp === 0 ? ' cell-dead' : '');
      badge.title = `${cell.type}${cell.module ? ' / ' + cell.module : ''} HP:${cell.hp}/${cell.hp_max}`;
      badge.textContent = cell.module ? MODULE_LABELS[cell.module] || cell.module.substring(0,3).toUpperCase() : cell.type.substring(0,3).toUpperCase();
      cellsEl.appendChild(badge);
    });
    card.appendChild(cellsEl);

    // Fire buttons for weapon cells
    const fireRow = document.createElement('div');
    fireRow.className = 'fire-buttons';
    ship.cells.forEach((cell, ci) => {
      if (cell.type !== 'weapon') return;
      const btn = document.createElement('button');
      btn.className = 'btn-fire';
      btn.textContent = `Fire ${MODULE_LABELS[cell.module] || cell.module}`;
      const disabled = cell.hp === 0 || cell.fired_this_turn || ship.state === 'sunk' || gameState.budget.supply === 0;
      btn.disabled = disabled;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        selectedShipIndex = idx;
        sendFire(idx, ci);
      });
      fireRow.appendChild(btn);
    });
    if (fireRow.children.length > 0) card.appendChild(fireRow);

    // Select on click
    card.addEventListener('click', () => {
      if (ship.state === 'sunk') return;
      selectedShipIndex = selectedShipIndex === idx ? null : idx;
      renderShipList();
      renderCanvas();
    });

    list.appendChild(card);
  });
}

function shipTypeName(ship) {
  const weapons = ship.cells.filter(c => c.type === 'weapon').map(c => c.module);
  if (weapons.includes('bomber')) return 'Carrier';
  if (ship.cells.length >= 5) return 'Battleship';
  if (weapons.includes('ballistic_missile') && ship.cells.length >= 3) return 'Cruiser';
  if (weapons.includes('torpedo') && ship.cells.length >= 3) return 'Destroyer';
  if (weapons.includes('mortar') && ship.cells.length <= 2) return 'Corvette';
  if (weapons.includes('ballistic_missile')) return 'Missile Boat';
  return 'Warship';
}

// ── Canvas rendering ──────────────────────────────────────────────────────────

function renderCanvas() {
  if (!gameState || !ctx) return;

  ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

  // Build grid lookup
  const gridMap = {};
  for (const cell of gameState.grid) {
    gridMap[`${cell.x},${cell.y}`] = cell;
  }

  // Build occupied map
  const playerOccupied = buildOccupiedMap(gameState.player_ships);
  const aiOccupied = buildOccupiedMap(gameState.ai_ships);

  // Draw terrain
  for (let y = 0; y < GRID_HEIGHT; y++) {
    for (let x = 0; x < GRID_WIDTH; x++) {
      const cell = gridMap[`${x},${y}`];
      const height = cell ? cell.height : 0;
      ctx.fillStyle = TERRAIN_COLORS[height] || '#1a3a5c';
      ctx.fillRect(x * CELL, y * CELL, CELL, CELL);

      // Grid line
      ctx.strokeStyle = 'rgba(255,255,255,0.05)';
      ctx.lineWidth = 0.5;
      ctx.strokeRect(x * CELL, y * CELL, CELL, CELL);

      // Objects
      if (cell && cell.obj) {
        drawObject(x, y, cell.obj);
      }

      // Effects
      if (cell && cell.effects && cell.effects.includes('fire')) {
        drawFire(x, y);
      }
    }
  }

  // Draw AI ships
  gameState.ai_ships.forEach((ship, idx) => {
    if (ship.state === 'sunk') return;
    drawShip(ship, false, false);
  });

  // Draw player ships
  gameState.player_ships.forEach((ship, idx) => {
    if (ship.state === 'sunk') return;
    const isSelected = selectedShipIndex === idx;
    drawShip(ship, true, isSelected);
  });

  // Draw markers
  for (const cell of gameState.grid) {
    if (cell.markers && cell.markers.length > 0) {
      for (const marker of cell.markers) {
        drawMarker(cell.x, cell.y, marker);
      }
    }
  }

  // Hovered cell highlight
  if (hoveredCell) {
    ctx.strokeStyle = 'rgba(255,255,255,0.4)';
    ctx.lineWidth = 2;
    ctx.strokeRect(hoveredCell.x * CELL + 1, hoveredCell.y * CELL + 1, CELL - 2, CELL - 2);
  }

  // Selection highlight on selected ship cells
  if (selectedShipIndex !== null) {
    const ship = gameState.player_ships[selectedShipIndex];
    if (ship && ship.state !== 'sunk') {
      const positions = getOccupiedPositions(ship);
      positions.forEach(pos => {
        ctx.strokeStyle = '#5a9aff';
        ctx.lineWidth = 2;
        ctx.strokeRect(pos.x * CELL + 1, pos.y * CELL + 1, CELL - 2, CELL - 2);
      });
    }
  }
}

function buildOccupiedMap(ships) {
  const map = {};
  ships.forEach((ship, shipIdx) => {
    if (ship.state === 'sunk') return;
    const positions = getOccupiedPositions(ship);
    positions.forEach((pos, cellIdx) => {
      map[`${pos.x},${pos.y}`] = { shipIdx, cellIdx, ship };
    });
  });
  return map;
}

function getOccupiedPositions(ship) {
  const deltas = { N: [0, -1], S: [0, 1], E: [1, 0], W: [-1, 0] };
  const [dx, dy] = deltas[ship.facing] || [1, 0];
  const bx = -dx, by = -dy;
  const positions = [];
  for (let i = 0; i < ship.cells.length; i++) {
    positions.push({
      x: ship.bridge_pos.x + bx * i,
      y: ship.bridge_pos.y + by * i,
    });
  }
  return positions;
}

function drawShip(ship, isPlayer, isSelected) {
  const positions = getOccupiedPositions(ship);
  const isDying = ship.state === 'dying';

  positions.forEach((pos, cellIdx) => {
    const cell = ship.cells[cellIdx];
    if (pos.x < 0 || pos.x >= GRID_WIDTH || pos.y < 0 || pos.y >= GRID_HEIGHT) return;

    const px = pos.x * CELL;
    const py = pos.y * CELL;

    // Base ship color
    let baseColor = isPlayer ? '#1a4a8a' : '#6a1a1a';
    if (isDying) baseColor = isPlayer ? '#3a2a00' : '#4a1a00';

    const isBridge = cellIdx === 0;
    if (isBridge) {
      baseColor = isPlayer ? '#2a6aff' : '#ff3a1a';
      if (isDying) baseColor = '#aa6600';
    }

    ctx.fillStyle = baseColor;
    const margin = 3;
    ctx.fillRect(px + margin, py + margin, CELL - margin * 2, CELL - margin * 2);

    // HP bar
    if (cell) {
      const hpRatio = cell.hp / cell.hp_max;
      const barW = CELL - margin * 2;
      const barH = 3;
      ctx.fillStyle = '#0a0a0a';
      ctx.fillRect(px + margin, py + CELL - margin - barH, barW, barH);
      ctx.fillStyle = hpRatio > 0.5 ? '#3aff3a' : hpRatio > 0.25 ? '#ffaa00' : '#ff3a3a';
      ctx.fillRect(px + margin, py + CELL - margin - barH, Math.round(barW * hpRatio), barH);
    }

    // Module label
    if (cell && cell.module) {
      ctx.fillStyle = 'rgba(255,255,255,0.8)';
      ctx.font = `bold ${Math.floor(CELL * 0.22)}px monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(MODULE_LABELS[cell.module] || '?', px + CELL / 2, py + CELL / 2);
    }

    // Bridge arrow indicator
    if (isBridge) {
      drawFacingArrow(px + CELL / 2, py + CELL / 2, ship.facing);
    }

    // Fired indicator
    if (cell && cell.fired_this_turn) {
      ctx.fillStyle = 'rgba(255,150,0,0.3)';
      ctx.fillRect(px + margin, py + margin, CELL - margin * 2, CELL - margin * 2);
    }
  });
}

function drawFacingArrow(cx, cy, facing) {
  const arrowLen = CELL * 0.28;
  const deltas = { N: [0, -1], S: [0, 1], E: [1, 0], W: [-1, 0] };
  const [dx, dy] = deltas[facing] || [1, 0];

  ctx.save();
  ctx.strokeStyle = 'rgba(255,255,255,0.6)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(cx - dx * arrowLen * 0.5, cy - dy * arrowLen * 0.5);
  ctx.lineTo(cx + dx * arrowLen * 0.5, cy + dy * arrowLen * 0.5);
  ctx.stroke();

  // Arrowhead
  const tipX = cx + dx * arrowLen * 0.5;
  const tipY = cy + dy * arrowLen * 0.5;
  const perpX = -dy * arrowLen * 0.3;
  const perpY = dx * arrowLen * 0.3;
  ctx.beginPath();
  ctx.moveTo(tipX, tipY);
  ctx.lineTo(tipX - dx * arrowLen * 0.4 + perpX, tipY - dy * arrowLen * 0.4 + perpY);
  ctx.lineTo(tipX - dx * arrowLen * 0.4 - perpX, tipY - dy * arrowLen * 0.4 - perpY);
  ctx.closePath();
  ctx.fillStyle = 'rgba(255,255,255,0.6)';
  ctx.fill();
  ctx.restore();
}

function drawMarker(gx, gy, marker) {
  const cx = gx * CELL + CELL / 2;
  const cy = gy * CELL + CELL / 2;
  const r = CELL * 0.2;

  if (marker === 'hit') {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = '#ff8800';
    ctx.fill();
    ctx.strokeStyle = '#ffcc00';
    ctx.lineWidth = 1.5;
    ctx.stroke();
  } else if (marker === 'miss') {
    const s = r;
    ctx.strokeStyle = '#556677';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx - s, cy - s);
    ctx.lineTo(cx + s, cy + s);
    ctx.moveTo(cx + s, cy - s);
    ctx.lineTo(cx - s, cy + s);
    ctx.stroke();
  }
}

function drawObject(gx, gy, obj) {
  const cx = gx * CELL + CELL / 2;
  const cy = gy * CELL + CELL / 2;
  ctx.font = `${Math.floor(CELL * 0.5)}px serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  if (obj === 'port') ctx.fillText('⚓', cx, cy);       // anchor
  else if (obj === 'oil_rig') ctx.fillText('🛢', cx, cy); // oil drum emoji fallback
  else if (obj === 'mine') ctx.fillText('☢', cx, cy);  // radiation/mine symbol
}

function drawFire(gx, gy) {
  const px = gx * CELL;
  const py = gy * CELL;
  ctx.fillStyle = 'rgba(255, 80, 0, 0.35)';
  ctx.fillRect(px, py, CELL, CELL);
  // Draw flame lines
  ctx.fillStyle = 'rgba(255, 160, 0, 0.5)';
  ctx.font = `${Math.floor(CELL * 0.5)}px serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('🔥', px + CELL / 2, py + CELL / 2);
}

// ── Event handlers ────────────────────────────────────────────────────────────

function onCanvasMouseMove(e) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const mx = (e.clientX - rect.left) * scaleX;
  const my = (e.clientY - rect.top) * scaleY;
  const gx = Math.floor(mx / CELL);
  const gy = Math.floor(my / CELL);
  if (gx >= 0 && gx < GRID_WIDTH && gy >= 0 && gy < GRID_HEIGHT) {
    hoveredCell = { x: gx, y: gy };
  } else {
    hoveredCell = null;
  }
  renderCanvas();
}

function onCanvasClick(e) {
  if (!gameState || !hoveredCell) return;

  // If there's a pending ballistic fire, fire at this cell
  if (pendingFire) {
    const { shipIndex, cellIndex } = pendingFire;
    pendingFire = null;
    const body = {
      type: 'fire',
      ship_index: shipIndex,
      module_cell_index: cellIndex,
      target: { x: hoveredCell.x, y: hoveredCell.y },
    };
    sendAction(body).then(res => {
      if (res && res.ok) setStatus('Ballistic missile fired!', 'ok');
      else if (res) setStatus('Fire failed: ' + res.error, 'err');
    });
    return;
  }

  // Check if a player ship is at clicked cell
  const { x, y } = hoveredCell;
  let found = null;
  gameState.player_ships.forEach((ship, idx) => {
    if (ship.state === 'sunk') return;
    const positions = getOccupiedPositions(ship);
    if (positions.some(p => p.x === x && p.y === y)) {
      found = idx;
    }
  });

  if (found !== null) {
    selectedShipIndex = selectedShipIndex === found ? null : found;
    renderShipList();
    renderCanvas();
    if (selectedShipIndex !== null) {
      setStatus(`Selected ship ${selectedShipIndex + 1}. Use WASD/arrows to move, Q/E to rotate.`, 'info');
    }
  }
}

function onKeyDown(e) {
  if (!gameState || gameState.phase !== 'player') return;

  // Don't intercept when typing in an input
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

  const key = e.key;

  const moveKeys = {
    'w': 'N', 'W': 'N', 'ArrowUp': 'N',
    's': 'S', 'S': 'S', 'ArrowDown': 'S',
    'a': 'W', 'A': 'W', 'ArrowLeft': 'W',
    'd': 'E', 'D': 'E', 'ArrowRight': 'E',
  };

  if (moveKeys[key]) {
    e.preventDefault();
    sendMove(moveKeys[key]);
    return;
  }

  if (key === 'q' || key === 'Q') {
    e.preventDefault();
    sendRotate(false);
    return;
  }

  if (key === 'e' || key === 'E') {
    e.preventDefault();
    sendRotate(true);
    return;
  }

  // Number keys 1-9 to select ship
  if (key >= '1' && key <= '9') {
    const idx = parseInt(key) - 1;
    if (gameState.player_ships[idx] && gameState.player_ships[idx].state !== 'sunk') {
      selectedShipIndex = idx;
      renderShipList();
      renderCanvas();
      setStatus(`Selected ship ${idx + 1}.`, 'info');
    }
  }

  // Enter or Space to end turn
  if (key === 'Enter') {
    e.preventDefault();
    sendEndTurn();
  }
}

// ── UI helpers ────────────────────────────────────────────────────────────────

function setStatus(msg, type) {
  const box = document.getElementById('status-box');
  box.className = 'status-' + (type || 'info');
  box.textContent = msg;
}

function showVictory(winner) {
  const overlay = document.getElementById('victory-overlay');
  const title = document.getElementById('victory-title');
  const subtitle = document.getElementById('victory-subtitle');
  overlay.classList.add('show');
  if (winner === 'player') {
    title.textContent = 'Victory!';
    title.className = 'victory-player';
    subtitle.textContent = 'You have defeated the enemy fleet!';
  } else {
    title.textContent = 'Defeat';
    title.className = 'victory-ai';
    subtitle.textContent = 'Your fleet has been destroyed.';
  }
}

function hideVictory() {
  document.getElementById('victory-overlay').classList.remove('show');
}
