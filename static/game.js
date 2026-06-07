// Armada Company v2 — game client
'use strict';

const GRID_WIDTH  = 15;
const GRID_HEIGHT = 32;
const CELL        = 36;
const CANVAS_WIDTH  = GRID_WIDTH  * CELL; // 540px
const CANVAS_HEIGHT = GRID_HEIGHT * CELL; // 1152px

const TERRAIN_COLORS = {
  0: '#1a3a5c', // DeepSea
  1: '#2d6a8a', // ShallowWater
  2: '#5a7a4a', // Land
  3: '#6a5a4a', // Mountain
};

const MODULE_LABELS = {
  torpedo:          'TRP',
  ballistic_missile:'BMS',
  mortar:           'MRT',
  bomber:           'BMB',
  aa_gun:           'AAG',
};

// ActionMode
const MODE_NONE            = 'none';
const MODE_MOVE_PATH       = 'move_path';
const MODE_TARGETING_MISSILE = 'targeting_missile';

// State
let sessionId        = null;
let gameState        = null;
let selectedShipIndex = null;
let activeModuleIndex = null; // which module is active in HUD
let hoveredCell       = null;
let canvas, ctx;
let actionMode       = MODE_NONE;
let pendingFireInfo  = null; // { shipIndex, cellIndex } for ballistic
let validMoveCells   = [];
let actionLog        = [];
let playerFuelMax    = 5;
let playerSupplyMax  = 5;

// ── Init ──────────────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', () => {
  canvas = document.getElementById('canvas');
  canvas.width  = CANVAS_WIDTH;
  canvas.height = CANVAS_HEIGHT;
  ctx = canvas.getContext('2d');

  canvas.addEventListener('mousemove', onCanvasMouseMove);
  canvas.addEventListener('click',     onCanvasClick);
  canvas.addEventListener('touchstart', onCanvasTouchStart, { passive: true });

  document.getElementById('btn-end-turn').addEventListener('click', sendEndTurn);
  document.getElementById('btn-new-game').addEventListener('click', startNewGame);
  document.getElementById('mobile-end-turn').addEventListener('click', sendEndTurn);

  document.addEventListener('keydown', onKeyDown);
  window.addEventListener('resize', resizeCanvas);

  resizeCanvas();
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
  activeModuleIndex = null;
  actionMode = MODE_NONE;
  pendingFireInfo = null;
  validMoveCells = [];
  actionLog = [];
  try {
    const data = await apiPost('/game/new', { admiral_profile: 'balanced' });
    sessionId = data.session_id;
    applyState(data.state);
    setStatus('Game started! Click a ship to select modules.', 'ok');
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
  if (res && res.ok) {
    addLog(`Ship moved ${direction}`);
    setStatus(`Ship moved ${direction}.`, 'ok');
    actionMode = MODE_NONE;
  }
}

async function sendMoveTo(shipIndex, targetX, targetY) {
  const res = await sendAction({
    type: 'move_to',
    ship_index: shipIndex,
    target: { x: targetX, y: targetY }
  });
  if (res && res.ok) {
    addLog(`Moved to (${targetX}, ${targetY})`);
    setStatus('Ship moved successfully!', 'ok');
    actionMode = MODE_NONE;
    validMoveCells = [];
    selectedShipIndex = null;
  } else if (res) {
    setStatus('Movement failed: ' + res.error, 'err');
  }
}

async function sendRotate(clockwise) {
  if (selectedShipIndex === null) { setStatus('Select a ship first.', 'err'); return; }
  const res = await sendAction({ type: 'rotate', ship_index: selectedShipIndex, clockwise });
  if (res && res.ok) {
    addLog(`Ship rotated ${clockwise ? 'CW' : 'CCW'}`);
    setStatus(`Ship rotated ${clockwise ? 'CW' : 'CCW'}.`, 'ok');
  }
}

async function sendFire(shipIndex, cellIndex) {
  const ship = gameState.player_ships[shipIndex];
  const cell = ship.cells[cellIndex];

  if (cell.module === 'ballistic_missile') {
    // Enter targeting mode
    pendingFireInfo = { shipIndex, cellIndex };
    actionMode = MODE_TARGETING_MISSILE;
    setStatus('Click target cell for Ballistic Missile (range 10).', 'info');
    renderCanvas();
    return;
  }

  const body = { type: 'fire', ship_index: shipIndex, module_cell_index: cellIndex };
  const res = await sendAction(body);
  if (res && res.ok) {
    addLog(`Fired ${MODULE_LABELS[cell.module] || cell.module}`);
    setStatus(`Fired ${MODULE_LABELS[cell.module] || cell.module}!`, 'ok');
  } else if (res) {
    setStatus('Fire failed: ' + res.error, 'err');
  }
}

async function sendEndTurn() {
  if (!gameState || gameState.phase !== 'player') return;
  setStatus('Ending turn...', 'info');
  activeModuleIndex = null;
  actionMode = MODE_NONE;
  pendingFireInfo = null;
  const res = await sendAction({ type: 'end_turn' });
  if (res && res.ok) {
    addLog('--- End of turn ---');
    setStatus('AI turn complete. Your move!', 'ok');
  }
}

function cancelMode() {
  activeModuleIndex = null;
  actionMode = MODE_NONE;
  pendingFireInfo = null;
  validMoveCells = [];
  setStatus('Action cancelled.', 'info');
  renderCanvas();
  renderMobileShipPanel();
}

// ── State application ─────────────────────────────────────────────────────────

function applyState(state) {
  gameState = state;
  if (state.player_stats) {
    playerFuelMax   = state.player_stats.fuel_per_turn;
    playerSupplyMax = state.player_stats.supply_per_turn;
  }
  updateSidebar();
  renderCanvas();
  updateMobileTopBar();
  renderMobileShipPanel();
  if (state.victory) showVictory(state.victory);
}

function addLog(msg) {
  actionLog.unshift(msg);
  if (actionLog.length > 5) actionLog.length = 5;
  const el = document.getElementById('action-log');
  if (el) el.innerHTML = actionLog.map(m => `<div>${m}</div>`).join('');
}

function updateSidebar() {
  if (!gameState) return;
  document.getElementById('turn-number').textContent = gameState.turn_number;
  document.getElementById('admiral-profile').textContent = gameState.player_profile || 'balanced';

  const fuel   = gameState.budget.fuel;
  const supply = gameState.budget.supply;

  document.getElementById('fuel-val').textContent   = `${fuel} / ${playerFuelMax}`;
  document.getElementById('supply-val').textContent = `${supply} / ${playerSupplyMax}`;
  document.getElementById('fuel-bar').style.width   = `${Math.min(100, (fuel / playerFuelMax) * 100)}%`;
  document.getElementById('supply-bar').style.width = `${Math.min(100, (supply / playerSupplyMax) * 100)}%`;

  const phase   = gameState.phase;
  const phaseEl = document.getElementById('turn-phase');
  phaseEl.textContent = phase === 'player' ? 'YOUR TURN' : 'AI TURN';
  phaseEl.style.background = phase === 'player' ? '#1a3a5a' : '#3a1a1a';
  phaseEl.style.color       = phase === 'player' ? '#6aaaff' : '#ff6a6a';

  const endBtn = document.getElementById('btn-end-turn');
  if (endBtn) endBtn.disabled = (phase !== 'player');

  renderShipList();
}

function renderShipList() {
  const list = document.getElementById('ship-list');
  list.innerHTML = '';

  gameState.player_ships.forEach((ship, idx) => {
    const isDead  = ship.state === 'dead';
    const isDying = ship.state === 'dying';
    const card = document.createElement('div');
    card.className = 'ship-card' +
      (isDead  ? ' dead'     : '') +
      (isDying ? ' dying'    : '') +
      (selectedShipIndex === idx ? ' selected' : '');

    const header = document.createElement('div');
    header.className = 'ship-card-header';

    const nameEl  = document.createElement('span');
    nameEl.className = 'ship-name';
    nameEl.textContent = shipTypeName(ship);

    const stateEl = document.createElement('span');
    stateEl.className = `ship-state state-${ship.state}`;
    stateEl.textContent = ship.state.toUpperCase();

    header.appendChild(nameEl);
    header.appendChild(stateEl);
    card.appendChild(header);

    const cellsEl = document.createElement('div');
    cellsEl.className = 'ship-cells';
    ship.cells.forEach(cell => {
      const badge = document.createElement('span');
      badge.className = `cell-badge cell-${cell.type}` + (cell.hp === 0 ? ' cell-dead' : '');
      badge.title = `${cell.type}${cell.module ? ' / ' + cell.module : ''} HP:${cell.hp}/${cell.hp_max}`;
      badge.textContent = cell.module
        ? MODULE_LABELS[cell.module] || cell.module.substring(0,3).toUpperCase()
        : cell.type.substring(0,3).toUpperCase();
      cellsEl.appendChild(badge);
    });
    card.appendChild(cellsEl);

    const fireRow = document.createElement('div');
    fireRow.className = 'fire-buttons';
    ship.cells.forEach((cell, ci) => {
      if (cell.type !== 'weapon') return;
      const btn = document.createElement('button');
      btn.className = 'btn-fire';
      btn.textContent = `Fire ${MODULE_LABELS[cell.module] || cell.module}`;
      const disabled = cell.hp === 0 || cell.fired_this_turn || isDead ||
                       gameState.budget.supply === 0 || ship.state === 'dying' && isDead;
      btn.disabled = disabled;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        selectedShipIndex = idx;
        sendFire(idx, ci);
      });
      fireRow.appendChild(btn);
    });
    if (fireRow.children.length > 0) card.appendChild(fireRow);

    card.addEventListener('click', () => {
      if (isDead) return;
      selectedShipIndex = (selectedShipIndex === idx) ? null : idx;
      actionMode = MODE_NONE;
      renderShipList();
      renderCanvas();
      renderMobileShipPanel();
    });

    list.appendChild(card);
  });
}

function shipTypeName(ship) {
  const weapons = ship.cells.filter(c => c.type === 'weapon').map(c => c.module);
  const size = ship.cells.length;
  if (weapons.includes('bomber'))                             return 'Carrier';
  if (size >= 4 && weapons.includes('mortar'))               return 'Battleship';
  if (weapons.includes('ballistic_missile') && size >= 3)    return 'Cruiser';
  if (weapons.includes('torpedo') && size >= 3)              return 'Destroyer';
  if (weapons.includes('ballistic_missile') && size <= 2)    return 'Corvette';
  if (weapons.includes('torpedo') && size <= 2)              return 'Missile Boat';
  return 'Warship';
}

// ── Path finding ──────────────────────────────────────────────────────────────

function getReachableCells(ship) {
  const fuel = gameState.budget.fuel;
  const size = ship.cells.length;
  const startup = size;
  if (fuel < startup) return []; // Can't even start

  const maxDist = fuel - startup; // How many cells can move after startup
  const reachable = new Set();
  const queue = [{x: ship.bridge_pos.x, y: ship.bridge_pos.y, dist: 0}];
  const visited = new Set([`${ship.bridge_pos.x},${ship.bridge_pos.y}`]);

  // Build occupied set
  const occupied = {};
  gameState.player_ships.concat(gameState.ai_ships).forEach(s => {
    if (s.state === 'dead') return;
    getOccupiedPositions(s).forEach(p => {
      occupied[`${p.x},${p.y}`] = true;
    });
  });
  delete occupied[`${ship.bridge_pos.x},${ship.bridge_pos.y}`];

  // BFS
  while (queue.length > 0) {
    const {x, y, dist} = queue.shift();
    if (dist > maxDist) continue;

    for (const [dx, dy] of [[0,1],[0,-1],[1,0],[-1,0]]) {
      const nx = x + dx, ny = y + dy;
      const key = `${nx},${ny}`;

      if (visited.has(key)) continue;
      if (nx < 0 || nx >= GRID_WIDTH || ny < 0 || ny > 14) continue; // Player zone
      if (occupied[key]) continue;

      const cell = gameState.grid.find(c => c.x === nx && c.y === ny);
      if (!cell) continue;
      // Land=2, Mountain=3
      if (cell.height === 2 || cell.height === 3) continue;
      // Shallow water ok for now (check draft if needed)
      if (cell.obj && cell.obj !== 'port' && cell.obj !== 'oil_rig') continue;

      visited.add(key);
      reachable.add(key);
      const nextDist = dist + 1;
      if (nextDist <= maxDist) {
        queue.push({x: nx, y: ny, dist: nextDist});
      }
    }
  }

  return Array.from(reachable).map(k => {
    const [x, y] = k.split(',').map(Number);
    return {x, y};
  });
}

// ── Canvas rendering ──────────────────────────────────────────────────────────

function renderCanvas() {
  if (!gameState || !ctx) return;

  ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

  const gridMap = {};
  for (const cell of gameState.grid) {
    gridMap[`${cell.x},${cell.y}`] = cell;
  }

  const playerOccupied = buildOccupiedMap(gameState.player_ships);
  const aiOccupied     = buildOccupiedMap(gameState.ai_ships);

  // Draw terrain
  for (let y = 0; y < GRID_HEIGHT; y++) {
    for (let x = 0; x < GRID_WIDTH; x++) {
      const cell   = gridMap[`${x},${y}`];
      const height = cell ? cell.height : 0;
      ctx.fillStyle = TERRAIN_COLORS[height] || '#1a3a5c';
      ctx.fillRect(x * CELL, y * CELL, CELL, CELL);

      ctx.strokeStyle = 'rgba(255,255,255,0.05)';
      ctx.lineWidth   = 0.5;
      ctx.strokeRect(x * CELL, y * CELL, CELL, CELL);

      if (cell && cell.obj) drawObject(x, y, cell.obj);
      if (cell && cell.effects && cell.effects.includes('fire')) drawFire(x, y);
    }
  }

  // Zone divider lines
  ctx.strokeStyle = 'rgba(100,180,255,0.15)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, 15 * CELL); ctx.lineTo(CANVAS_WIDTH, 15 * CELL);
  ctx.moveTo(0, 17 * CELL); ctx.lineTo(CANVAS_WIDTH, 17 * CELL);
  ctx.stroke();

  // MovePath overlay (new path-based movement)
  if (actionMode === MODE_MOVE_PATH && selectedShipIndex !== null) {
    drawMovePathOverlay();
  }

  // TargetingMissile overlay
  if (actionMode === MODE_TARGETING_MISSILE && pendingFireInfo) {
    drawMissileOverlay();
  }

  // AI ships
  gameState.ai_ships.forEach(ship => {
    if (ship.state === 'dead') return;
    drawShip(ship, false, false);
  });

  // Player ships
  gameState.player_ships.forEach((ship, idx) => {
    if (ship.state === 'dead') return;
    drawShip(ship, true, selectedShipIndex === idx);
  });


  // Markers
  for (const cell of gameState.grid) {
    if (cell.markers && cell.markers.length > 0) {
      for (const marker of cell.markers) drawMarker(cell.x, cell.y, marker);
    }
  }

  // Hover highlight
  if (hoveredCell) {
    ctx.strokeStyle = 'rgba(255,255,255,0.35)';
    ctx.lineWidth   = 1.5;
    ctx.strokeRect(hoveredCell.x * CELL + 1, hoveredCell.y * CELL + 1, CELL - 2, CELL - 2);
  }

  // Selection highlight
  if (selectedShipIndex !== null) {
    const ship = gameState.player_ships[selectedShipIndex];
    if (ship && ship.state !== 'dead') {
      const positions = getOccupiedPositions(ship);
      positions.forEach(pos => {
        ctx.strokeStyle = '#5a9aff';
        ctx.lineWidth   = 2;
        ctx.strokeRect(pos.x * CELL + 1, pos.y * CELL + 1, CELL - 2, CELL - 2);
      });
    }
  }
}

function drawMovePathOverlay() {
  validMoveCells.forEach(cell => {
    ctx.fillStyle = 'rgba(0,200,80,0.2)';
    ctx.fillRect(cell.x * CELL, cell.y * CELL, CELL, CELL);
    ctx.strokeStyle = 'rgba(0,220,80,0.7)';
    ctx.lineWidth = 2;
    ctx.strokeRect(cell.x * CELL, cell.y * CELL, CELL, CELL);
  });
}

function drawMissileOverlay() {
  const ship = gameState.player_ships[pendingFireInfo.shipIndex];
  if (!ship) return;
  const bx = ship.bridge_pos.x, by = ship.bridge_pos.y;
  for (let y = 0; y < GRID_HEIGHT; y++) {
    for (let x = 0; x < GRID_WIDTH; x++) {
      const dist = Math.abs(x - bx) + Math.abs(y - by);
      if (dist <= 10) {
        ctx.strokeStyle = 'rgba(255,160,0,0.4)';
        ctx.lineWidth   = 1;
        ctx.strokeRect(x * CELL, y * CELL, CELL, CELL);
      }
    }
  }
  // Preview explosion on hover
  if (hoveredCell) {
    const dist = Math.abs(hoveredCell.x - bx) + Math.abs(hoveredCell.y - by);
    if (dist <= 10) {
      [[0,0],[1,0],[-1,0],[0,1],[0,-1]].forEach(([dx, dy]) => {
        const px = hoveredCell.x + dx, py = hoveredCell.y + dy;
        if (px >= 0 && px < GRID_WIDTH && py >= 0 && py < GRID_HEIGHT) {
          ctx.fillStyle = 'rgba(255,120,0,0.3)';
          ctx.fillRect(px * CELL, py * CELL, CELL, CELL);
        }
      });
    }
  }
}

function buildOccupiedMap(ships) {
  const map = {};
  ships.forEach((ship, shipIdx) => {
    if (ship.state === 'dead') return;
    getOccupiedPositions(ship).forEach((pos, cellIdx) => {
      map[`${pos.x},${pos.y}`] = { shipIdx, cellIdx, ship };
    });
  });
  return map;
}

function getOccupiedPositions(ship) {
  const deltas = { N:[0,-1], S:[0,1], E:[1,0], W:[-1,0] };
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

function _hpColor(ratio) {
  if (ratio > 0.66) return null;         // normal — use base color
  if (ratio > 0.33) return '#2a4a00';    // damaged_light
  return '#4a1000';                       // damaged_heavy
}

function drawShip(ship, isPlayer, isSelected) {
  const positions = getOccupiedPositions(ship);
  const isDying   = ship.state === 'dying';
  const isHoriz   = ship.facing === 'E' || ship.facing === 'W';

  positions.forEach((pos, cellIdx) => {
    const cell = ship.cells[cellIdx];
    if (pos.x < 0 || pos.x >= GRID_WIDTH || pos.y < 0 || pos.y >= GRID_HEIGHT) return;

    const px = pos.x * CELL;
    const py = pos.y * CELL;
    const isBridge = cellIdx === 0;

    // Base color
    let baseColor = isPlayer ? '#1a4a8a' : '#6a1a1a';
    if (isBridge) baseColor = isPlayer ? '#2a6aff' : '#ff3a1a';
    if (isDying)  baseColor = isBridge ? '#aa6600' : (isPlayer ? '#3a2a00' : '#4a1a00');

    // Damage tinting
    if (cell && !isDying) {
      const ratio = cell.hp / cell.hp_max;
      const dmgColor = _hpColor(ratio);
      if (dmgColor) baseColor = dmgColor;
      if (isBridge && dmgColor) baseColor = dmgColor; // bridge also tinted
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
      ctx.fillStyle = 'rgba(255,255,255,0.85)';
      ctx.font = `bold ${Math.floor(CELL * 0.22)}px monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(MODULE_LABELS[cell.module] || '?', px + CELL / 2, py + CELL / 2);
    }

    // Bridge arrow
    if (isBridge) drawFacingArrow(px + CELL / 2, py + CELL / 2, ship.facing);

    // Fired indicator
    if (cell && cell.fired_this_turn) {
      ctx.fillStyle = 'rgba(255,150,0,0.3)';
      ctx.fillRect(px + margin, py + margin, CELL - margin * 2, CELL - margin * 2);
    }

    // Dying flash overlay
    if (isDying) {
      ctx.fillStyle = 'rgba(0,0,0,0.4)';
      ctx.fillRect(px + margin, py + margin, CELL - margin * 2, CELL - margin * 2);
    }
  });
}

function drawFacingArrow(cx, cy, facing) {
  const arrowLen = CELL * 0.28;
  const deltas = { N:[0,-1], S:[0,1], E:[1,0], W:[-1,0] };
  const [dx, dy] = deltas[facing] || [1, 0];

  ctx.save();
  ctx.strokeStyle = 'rgba(255,255,255,0.6)';
  ctx.lineWidth   = 1.5;
  ctx.beginPath();
  ctx.moveTo(cx - dx * arrowLen * 0.5, cy - dy * arrowLen * 0.5);
  ctx.lineTo(cx + dx * arrowLen * 0.5, cy + dy * arrowLen * 0.5);
  ctx.stroke();

  const tipX  = cx + dx * arrowLen * 0.5;
  const tipY  = cy + dy * arrowLen * 0.5;
  const perpX = -dy * arrowLen * 0.3;
  const perpY =  dx * arrowLen * 0.3;
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
  const r  = CELL * 0.2;

  if (marker === 'hit') {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle   = '#ff8800';
    ctx.fill();
    ctx.strokeStyle = '#ffcc00';
    ctx.lineWidth   = 1.5;
    ctx.stroke();
  } else if (marker === 'miss') {
    const s = r;
    ctx.strokeStyle = '#556677';
    ctx.lineWidth   = 2;
    ctx.beginPath();
    ctx.moveTo(cx - s, cy - s); ctx.lineTo(cx + s, cy + s);
    ctx.moveTo(cx + s, cy - s); ctx.lineTo(cx - s, cy + s);
    ctx.stroke();
  }
}

function drawObject(gx, gy, obj) {
  const cx = gx * CELL + CELL / 2;
  const cy = gy * CELL + CELL / 2;
  ctx.font = `${Math.floor(CELL * 0.5)}px serif`;
  ctx.textAlign     = 'center';
  ctx.textBaseline  = 'middle';
  if      (obj === 'port')    ctx.fillText('⚓', cx, cy);
  else if (obj === 'oil_rig') ctx.fillText('🛢', cx, cy);
  else if (obj === 'mine') {
    // Draw mine: circle with spikes
    ctx.beginPath();
    ctx.arc(cx, cy, CELL * 0.18, 0, Math.PI * 2);
    ctx.fillStyle = '#333';
    ctx.fill();
    ctx.strokeStyle = '#888';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    for (let a = 0; a < Math.PI * 2; a += Math.PI / 4) {
      const r1 = CELL * 0.18, r2 = CELL * 0.28;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
      ctx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2);
      ctx.stroke();
    }
  }
  else if (obj === 'npc_ship') {
    ctx.fillStyle = '#888';
    ctx.fillText('⛵', cx, cy);
  }
}

function drawFire(gx, gy) {
  const px = gx * CELL;
  const py = gy * CELL;
  ctx.fillStyle = 'rgba(255, 80, 0, 0.35)';
  ctx.fillRect(px, py, CELL, CELL);
  ctx.font = `${Math.floor(CELL * 0.5)}px serif`;
  ctx.textAlign     = 'center';
  ctx.textBaseline  = 'middle';
  ctx.fillText('🔥', px + CELL / 2, py + CELL / 2);
}

// ── Event handlers ────────────────────────────────────────────────────────────

function onCanvasMouseMove(e) {
  const rect   = canvas.getBoundingClientRect();
  const scaleX = canvas.width  / rect.width;
  const scaleY = canvas.height / rect.height;
  const mx = (e.clientX - rect.left) * scaleX;
  const my = (e.clientY - rect.top)  * scaleY;
  const gx = Math.floor(mx / CELL);
  const gy = Math.floor(my / CELL);
  hoveredCell = (gx >= 0 && gx < GRID_WIDTH && gy >= 0 && gy < GRID_HEIGHT)
    ? { x: gx, y: gy } : null;
  renderCanvas();
}

function onCanvasClick(e) {
  if (!gameState || !hoveredCell) return;

  // TargetingMissile: fire at clicked cell
  if (actionMode === MODE_TARGETING_MISSILE && pendingFireInfo) {
    const { shipIndex, cellIndex } = pendingFireInfo;
    const ship = gameState.player_ships[shipIndex];
    const dist = Math.abs(hoveredCell.x - ship.bridge_pos.x) +
                 Math.abs(hoveredCell.y - ship.bridge_pos.y);
    if (dist > 10) {
      setStatus('Out of range (max 10).', 'err');
      return;
    }
    const body = {
      type: 'fire',
      ship_index: shipIndex,
      module_cell_index: cellIndex,
      target: { x: hoveredCell.x, y: hoveredCell.y },
    };
    pendingFireInfo = null;
    actionMode = MODE_NONE;
    sendAction(body).then(res => {
      if (res && res.ok) {
        addLog('Ballistic missile fired!');
        setStatus('Ballistic missile fired!', 'ok');
      } else if (res) {
        setStatus('Fire failed: ' + res.error, 'err');
      }
    });
    return;
  }

  // MovePath mode: click on green cell to move
  if (actionMode === MODE_MOVE_PATH && selectedShipIndex !== null) {
    const isReachable = validMoveCells.some(c => c.x === hoveredCell.x && c.y === hoveredCell.y);
    if (isReachable) {
      sendMoveTo(selectedShipIndex, hoveredCell.x, hoveredCell.y);
      return;
    }
    // Clicked elsewhere: cancel
    actionMode = MODE_NONE;
    validMoveCells = [];
    renderCanvas();
    return;
  }

  // Click player ship
  const { x, y } = hoveredCell;
  let found = null;
  let cellIndex = -1;
  gameState.player_ships.forEach((ship, idx) => {
    if (ship.state === 'dead') return;
    const positions = getOccupiedPositions(ship);
    positions.forEach((p, ci) => {
      if (p.x === x && p.y === y) {
        found = idx;
        cellIndex = ci;
      }
    });
  });

  if (found !== null) {
    selectedShipIndex = (selectedShipIndex === found) ? null : found;
    activeModuleIndex = null;
    actionMode = MODE_NONE;
    validMoveCells = [];
    renderCanvas();
    renderMobileShipPanel();
    if (selectedShipIndex !== null)
      setStatus(`Ship selected. Click modules in HUD to activate.`, 'info');
  }
}

function onKeyDown(e) {
  if (!gameState) return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

  const key = e.key;

  // Esc: cancel mode
  if (key === 'Escape') { cancelMode(); return; }

  if (gameState.phase !== 'player') return;

  const moveKeys = {
    'w':'N','W':'N','ArrowUp':'N',
    's':'S','S':'S','ArrowDown':'S',
    'a':'W','A':'W','ArrowLeft':'W',
    'd':'E','D':'E','ArrowRight':'E',
  };

  if (moveKeys[key]) {
    e.preventDefault();
    sendMove(moveKeys[key]);
    return;
  }

  // R: rotate CW, E: rotate CCW
  if (key === 'r' || key === 'R') { e.preventDefault(); sendRotate(true);  return; }
  if (key === 'e' || key === 'E') { e.preventDefault(); sendRotate(false); return; }

  // Number keys to select ship
  if (key >= '1' && key <= '9') {
    const idx = parseInt(key) - 1;
    if (gameState.player_ships[idx] && gameState.player_ships[idx].state !== 'dead') {
      selectedShipIndex = idx;
      actionMode = MODE_NONE;
      renderShipList();
      renderCanvas();
    }
    return;
  }

  // Space or Enter: end turn
  if (key === ' ' || key === 'Enter') {
    e.preventDefault();
    sendEndTurn();
  }
}

// ── UI helpers ─────────────────────────────────────────────────────────────────

function setStatus(msg, type) {
  const box = document.getElementById('status-box');
  box.className  = 'status-' + (type || 'info');
  box.textContent = msg;
}

function showVictory(winner) {
  const overlay  = document.getElementById('victory-overlay');
  const title    = document.getElementById('victory-title');
  const subtitle = document.getElementById('victory-subtitle');
  overlay.classList.add('show');
  if (winner === 'player') {
    title.textContent = 'Victory!';
    title.className   = 'victory-player';
    subtitle.textContent = 'You have defeated the enemy fleet!';
  } else {
    title.textContent = 'Defeat';
    title.className   = 'victory-ai';
    subtitle.textContent = 'Your fleet has been destroyed.';
  }
}

function hideVictory() {
  document.getElementById('victory-overlay').classList.remove('show');
}

// ── Mobile helpers ─────────────────────────────────────────────────────────────

function resizeCanvas() {
  const gameArea = document.getElementById('game-area');
  const topBar = document.getElementById('mobile-top-bar');
  const shipPanel = document.getElementById('mobile-ship-panel');

  const availableHeight = window.innerHeight -
                         (topBar ? topBar.offsetHeight : 0) -
                         (shipPanel ? shipPanel.offsetHeight : 0) - 16;
  const availableWidth = gameArea.clientWidth - 8;

  // Calculate size to fit in available space while maintaining aspect ratio
  const aspectRatio = CANVAS_WIDTH / CANVAS_HEIGHT;
  let w = availableWidth;
  let h = w / aspectRatio;

  if (h > availableHeight) {
    h = availableHeight;
    w = h * aspectRatio;
  }

  if (w > 0 && h > 0) {
    canvas.style.width  = w + 'px';
    canvas.style.height = h + 'px';
  }
}

function onCanvasTouchStart(e) {
  const touch  = e.touches[0];
  const rect   = canvas.getBoundingClientRect();
  const scaleX = canvas.width  / rect.width;
  const scaleY = canvas.height / rect.height;
  const gx = Math.floor((touch.clientX - rect.left) * scaleX / CELL);
  const gy = Math.floor((touch.clientY - rect.top)  * scaleY / CELL);
  hoveredCell = (gx >= 0 && gx < GRID_WIDTH && gy >= 0 && gy < GRID_HEIGHT)
    ? { x: gx, y: gy } : null;
}

function updateMobileTopBar() {
  if (!gameState) return;
  const num    = document.getElementById('mobile-turn-num');
  const fuel   = document.getElementById('mobile-fuel-val');
  const supply = document.getElementById('mobile-supply-val');
  const badge  = document.getElementById('mobile-phase-badge');
  if (!num) return;

  num.textContent    = gameState.turn_number;
  fuel.textContent   = gameState.budget.fuel;
  supply.textContent = gameState.budget.supply;

  const isPlayer = gameState.phase === 'player';
  badge.textContent  = isPlayer ? 'Your Turn' : 'AI Turn';
  badge.style.background = isPlayer ? '#1a3a5a' : '#3a1a1a';
  badge.style.color      = isPlayer ? '#6aaaff' : '#ff6a6a';
}

function renderMobileShipPanel() {
  const panel = document.getElementById('mobile-ship-panel');
  if (!panel) return;

  if (selectedShipIndex === null || !gameState) {
    panel.style.display = 'none';
    return;
  }

  const ship = gameState.player_ships[selectedShipIndex];
  if (!ship || ship.state === 'dead') {
    panel.style.display = 'none';
    return;
  }

  panel.style.display = 'block';
  document.getElementById('mobile-ship-name').textContent = shipTypeName(ship);
  const stateBadge = document.getElementById('mobile-ship-state-badge');
  stateBadge.textContent = ship.state.toUpperCase();
  stateBadge.className   = `ship-state state-${ship.state}`;

  const row = document.getElementById('mobile-ship-cells-row');
  row.innerHTML = '';

  ship.cells.forEach((cell, ci) => {
    const isDead    = cell.hp === 0;
    const isFired   = !!cell.fired_this_turn;
    const isWeapon  = cell.type === 'weapon';
    const isBridge  = ci === 0;
    const noSupply  = isWeapon && gameState.budget.supply === 0;
    const isActive  = activeModuleIndex === ci;
    const canActivate = !isDead && gameState.phase === 'player' &&
                       (isBridge && !ship.moved_this_turn || isWeapon && !isFired && !noSupply);

    const btn = document.createElement('button');
    let cls = `mobile-cell-btn type-${cell.type}`;
    if (isDead)     cls += ' cell-dead';
    else if (isFired)    cls += ' cell-fired';
    else if (noSupply)   cls += ' cell-no-supply';
    if (isActive)   cls += ' active';
    btn.className = cls;
    btn.disabled = !canActivate;

    const labelEl = document.createElement('span');
    labelEl.className   = 'mcb-label';
    labelEl.textContent = cell.module
      ? (MODULE_LABELS[cell.module] || cell.module.substring(0, 3).toUpperCase())
      : cell.type.substring(0, 3).toUpperCase();

    const typeEl = document.createElement('span');
    typeEl.className   = 'mcb-type';
    typeEl.textContent = cell.type;

    const hpEl = document.createElement('span');
    hpEl.className = 'mcb-hp';
    if (isDead) {
      hpEl.textContent = '✕ sunk';
    } else if (isFired) {
      hpEl.textContent = 'fired';
      hpEl.style.color = '#ffaa00';
    } else {
      const ratio = cell.hp / cell.hp_max;
      hpEl.textContent = `${cell.hp}/${cell.hp_max}`;
      hpEl.className  += ratio > 0.5 ? ' hp-ok' : ratio > 0.25 ? ' hp-medium' : ' hp-low';
    }

    btn.appendChild(labelEl);
    btn.appendChild(typeEl);
    btn.appendChild(hpEl);

    if (canActivate) {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        onModuleClick(selectedShipIndex, ci);
      });
    }

    row.appendChild(btn);
  });
}

function onModuleClick(shipIndex, cellIndex) {
  const ship = gameState.player_ships[shipIndex];
  if (!ship) return;
  const cell = ship.cells[cellIndex];
  const isBridge = cellIndex === 0;
  const isWeapon = cell.type === 'weapon';

  // Deactivate if clicking same module again
  if (activeModuleIndex === cellIndex) {
    activeModuleIndex = null;
    actionMode = MODE_NONE;
    validMoveCells = [];
    setStatus('Cancelled.', 'info');
    renderMobileShipPanel();
    renderCanvas();
    return;
  }

  // Activate new module
  activeModuleIndex = cellIndex;

  if (isBridge && !ship.moved_this_turn) {
    validMoveCells = getReachableCells(ship);
    actionMode = MODE_MOVE_PATH;
    setStatus(`Move mode active. Click green cells to move. Click bridge again to cancel.`, 'info');
    renderMobileShipPanel();
    renderCanvas();
  } else if (isWeapon && !cell.fired_this_turn && gameState.budget.supply > 0) {
    sendFire(shipIndex, cellIndex);
  }
}
