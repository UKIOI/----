const canvas = document.querySelector("#canvas");
const ctx = canvas.getContext("2d");
const menu = document.querySelector("#menu");
const game = document.querySelector("#game");
const statusLabel = document.querySelector("#status");
const powerLabel = document.querySelector("#powerups");
const rolePanel = document.querySelector("#roles");
const joystick = document.querySelector("#joystick");
const joystickKnob = document.querySelector("#joystickKnob");
const aimJoystick = document.querySelector("#aimJoystick");
const aimJoystickKnob = document.querySelector("#aimJoystickKnob");
const skillButton = document.querySelector("#skillButton");
const botToggle = document.querySelector("#botToggle");
const botPanel = document.querySelector("#botPanel");
const botClose = document.querySelector("#botClose");
const botCount = document.querySelector("#botCount");
const botDifficulty = document.querySelector("#botDifficulty");
const applyBots = document.querySelector("#applyBots");
const botSummary = document.querySelector("#botSummary");
const chatToggle = document.querySelector("#chatToggle");
const chatUnread = document.querySelector("#chatUnread");
const chatPanel = document.querySelector("#chatPanel");
const chatClose = document.querySelector("#chatClose");
const chatMessages = document.querySelector("#chatMessages");
const chatForm = document.querySelector("#chatForm");
const chatInput = document.querySelector("#chatInput");
const MODE_NAMES = { classic: "经典模式", items: "多道具模式", pure: "纯净模式", profession: "职业模式" };
const ROLE_NAMES = { tank: "坦克", mage: "法师", sniper: "狙击手", necromancer: "死灵法师", weaponmaster: "武器大师", paladin: "圣骑士" };
const POWERUPS = {
  damage: { icon: "⚔", name: "强化伤害", color: "#ff5d73" }, rapid: { icon: "⚡", name: "高速射击", color: "#ffd166" },
  multishot: { icon: "✦", name: "三重子弹", color: "#64a8ff" }, laser: { icon: "▰", name: "半血激光", color: "#c77dff" },
  shield: { icon: "⬡", name: "强化护盾", color: "#55e6ff" }, speed: { icon: "➤", name: "移动加速", color: "#77ff88" },
  beam: { icon: "≋", name: "高能光束", color: "#ff72e1" },
  health: { icon: "+", name: "生命补给", color: "#ff4268" }, ricochet: { icon: "↗", name: "反弹弹药", color: "#ff9f43" },
  cannon: { icon: "●", name: "攻城大炮", color: "#ff7b39" }, minion: { icon: "◉", name: "战斗随从", color: "#72f1d0" },
  invincible: { icon: "✧", name: "神圣无敌", color: "#ffe17a" },
};
let ws, myId = null, requestedMode = "classic", world = { width: 1600, height: 900 };
let state = { players: [], bullets: [], lasers: [], explosions: [], pickups: [], obstacles: [] };
let keys = {}, mouse = { x: 0, y: 0, down: false }, touchMove = { x: 0, y: 0 }, touchAim = { x: 1, y: 0, active: false };
let movePointer = null, aimPointer = null;
const mobileMode = matchMedia("(pointer: coarse)").matches || navigator.maxTouchPoints > 0;
const viewScale = mobileMode ? .72 : 1;
let camera = { x: 0, y: 0 }, lastSend = 0, receivedState = false, stateReceivedAt = performance.now();
let unreadChats = 0;
let predictedSelf = null, lastFrame = performance.now(), lastPing = 0, latency = null;
let predictionWasMoving = false, predictionHoldUntil = 0, predictionBlocked = false;
let viewWidth = innerWidth, viewHeight = innerHeight, sceneWidth = innerWidth / viewScale, sceneHeight = innerHeight / viewScale;
const speedTrails = new Map();
const smoothPositions = new Map();
function resize() {
  const viewport = window.visualViewport;
  const ratio = Math.min(devicePixelRatio || 1, mobileMode ? 1.5 : 2);
  viewWidth = Math.round(viewport?.width || innerWidth); viewHeight = Math.round(viewport?.height || innerHeight);
  sceneWidth = viewWidth / viewScale; sceneHeight = viewHeight / viewScale;
  canvas.style.width = `${viewWidth}px`; canvas.style.height = `${viewHeight}px`;
  canvas.width = Math.round(viewWidth * ratio); canvas.height = Math.round(viewHeight * ratio);
  document.documentElement.style.setProperty("--view-width", `${viewWidth}px`);
  document.documentElement.style.setProperty("--view-height", `${viewHeight}px`);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
}
addEventListener("resize", resize); addEventListener("orientationchange", () => setTimeout(resize, 150));
window.visualViewport?.addEventListener("resize", resize); resize();
document.querySelector("#join").onclick = connect;
function connect() {
  document.querySelector("#join").disabled = true;
  requestedMode = document.querySelector("#mode").value;
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  statusLabel.textContent = "连接中…";
  ws.onopen = () => ws.send(JSON.stringify({ type: "join", name: document.querySelector("#name").value, room: document.querySelector("#room").value, mode: document.querySelector("#mode").value }));
  ws.onmessage = event => {
    const data = JSON.parse(event.data);
    if (data.type === "welcome") {
      if (data.protocol !== 11 || data.mode !== requestedMode) {
        alert("客户端与服务器版本不一致，请重启服务器并强制刷新页面");
        ws.close();
        return;
      }
      myId = data.id; world = data; state.obstacles = data.obstacles || []; predictedSelf = null; predictionWasMoving = false; predictionHoldUntil = 0; lastPing = 0; menu.hidden = true; game.hidden = false; canvas.tabIndex = 0; canvas.focus();
      document.querySelector("#roomLabel").textContent = `房间 ${data.room} · ${MODE_NAMES[data.mode]}`;
      statusLabel.textContent = data.mode === "profession" ? "请选择职业" : "正在载入战场…";
      rolePanel.hidden = data.mode !== "profession";
    } else if (data.type === "state") {
      const destroyed = new Map(data.destroyed || []);
      data.obstacles = (state.obstacles || []).map(obstacle => ({ ...obstacle, active: !destroyed.has(obstacle.id), restore: destroyed.get(obstacle.id) || 0 }));
      reconcilePrediction(data.players.find(player => player.id === myId));
      recordSpeedTrails(data.players); state = data; stateReceivedAt = performance.now(); receivedState = true; const me = data.players.find(player => player.id === myId);
      if (requestedMode === "profession") rolePanel.hidden = me?.ready === true;
      const isPaladin = me?.ready && me.role === "paladin";
      skillButton.hidden = !isPaladin;
      if (isPaladin) { skillButton.disabled = me.ability_cooldown > 0; skillButton.textContent = me.ability_cooldown > 0 ? `圣盾 ${Math.ceil(me.ability_cooldown)}s` : "圣盾"; }
      const pingText = latency === null ? "" : ` · ${latency}ms`, botTotal = data.bot_count || 0;
      botSummary.textContent = botTotal ? `当前 ${botTotal} 个人机 · ${{ easy: "简单", normal: "普通", hard: "困难" }[data.bot_difficulty] || "普通"}` : "当前没有人机";
      statusLabel.textContent = me && !me.ready ? "请选择职业" : `${me?.role ? ROLE_NAMES[me.role] + " · " : ""}已连接 · ${botTotal} 个人机${pingText}`; updatePowerLabel();
    } else if (data.type === "pong") {
      const sample = performance.now() - Number(data.sent);
      if (Number.isFinite(sample) && sample >= 0) latency = Math.round(latency === null ? sample : latency * .7 + sample * .3);
    } else if (data.type === "chat") {
      appendChatMessage(data);
    } else if (data.type === "error") alert(data.message);
  };
  ws.onerror = () => { document.querySelector("#join").disabled = false; alert("连接失败，请确认服务器仍在运行"); };
  ws.onclose = () => { statusLabel.textContent = "连接断开，请刷新重试"; document.querySelector("#join").disabled = false; };
}
document.querySelectorAll("[data-role]").forEach(button => button.onclick = () => {
  ws?.send(JSON.stringify({ type: "select_role", role: button.dataset.role }));
  statusLabel.textContent = "正在进入战场…";
});
skillButton.addEventListener("pointerdown", event => {
  event.preventDefault();
  if (!skillButton.disabled) ws?.send(JSON.stringify({ type: "ability" }));
});
function stopGameInput() {
  keys = {}; mouse.down = false; touchMove.x = 0; touchMove.y = 0; touchAim.active = false;
  joystickKnob.style.left = "50%"; joystickKnob.style.top = "50%";
  aimJoystickKnob.style.left = "50%"; aimJoystickKnob.style.top = "50%";
  sendInput(performance.now(), true);
}
function openChat() {
  botPanel.hidden = true; botToggle.hidden = false;
  chatPanel.hidden = false; chatToggle.hidden = true; unreadChats = 0; chatUnread.hidden = true;
  stopGameInput(); setTimeout(() => chatInput.focus(), 0);
}
function closeChatPanel() {
  chatPanel.hidden = true; chatToggle.hidden = false; chatInput.blur(); canvas.focus({ preventScroll: true });
}
function appendChatMessage(data) {
  chatMessages.querySelector(".chat-tip")?.remove();
  const line = document.createElement("p"), name = document.createElement("b"), message = document.createElement("span");
  line.className = "chat-message"; name.textContent = `${data.name}:`; name.style.color = data.color; message.textContent = data.message;
  line.append(name, message); chatMessages.append(line);
  while (chatMessages.children.length > 60) chatMessages.firstElementChild.remove();
  chatMessages.scrollTop = chatMessages.scrollHeight;
  if (chatPanel.hidden) { unreadChats += 1; chatUnread.hidden = false; chatUnread.title = `${unreadChats} 条未读消息`; }
}
chatToggle.addEventListener("click", openChat);
chatClose.addEventListener("click", closeChatPanel);
chatForm.addEventListener("submit", event => {
  event.preventDefault(); const message = chatInput.value.trim();
  if (!message || !ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "chat", message: message.slice(0, 120) })); chatInput.value = ""; chatInput.focus();
});
chatInput.addEventListener("keydown", event => { event.stopPropagation(); if (event.key === "Escape") { event.preventDefault(); closeChatPanel(); } });
chatInput.addEventListener("keyup", event => event.stopPropagation());
function openBotPanel() { chatPanel.hidden = true; chatToggle.hidden = false; botPanel.hidden = false; botToggle.hidden = true; stopGameInput(); }
function closeBotPanel() { botPanel.hidden = true; botToggle.hidden = false; canvas.focus({ preventScroll: true }); }
botToggle.addEventListener("click", openBotPanel);
botClose.addEventListener("click", closeBotPanel);
botPanel.addEventListener("keydown", event => event.stopPropagation());
botPanel.addEventListener("keyup", event => event.stopPropagation());
applyBots.addEventListener("click", () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "configure_bots", count: Number(botCount.value), difficulty: botDifficulty.value }));
  closeBotPanel();
});
function updatePowerLabel() {
  const me = state.players.find(player => player.id === myId), effects = Object.entries(me?.effects || {});
  const labels = effects.map(([kind, seconds]) => { const effect = POWERUPS[kind] || { icon: "◆", name: kind }; return `${effect.icon} ${effect.name} ${seconds.toFixed(1)}s`; });
  if (me?.minions?.length) labels.push(`◉ 战斗随从 ×${me.minions.length}`);
  if (me?.role === "weaponmaster" && !effects.some(([kind]) => ["multishot", "laser", "beam", "ricochet", "cannon"].includes(kind))) labels.push(`⚒ 随机武器 ${Math.ceil(me.weapon_cooldown)}s`);
  if (me?.role === "paladin" && !me.effects?.invincible) labels.push(me.ability_cooldown > 0 ? `✧ 圣盾冷却 ${Math.ceil(me.ability_cooldown)}s` : "✧ 圣盾已就绪（空格）");
  powerLabel.textContent = labels.length ? labels.join("　") : "寻找地图上的发光道具";
}
const KEY_CODES = { KeyW: "w", KeyA: "a", KeyS: "s", KeyD: "d", ArrowUp: "arrowup", ArrowDown: "arrowdown", ArrowLeft: "arrowleft", ArrowRight: "arrowright", Space: " " };
function updateKey(event, pressed) {
  if (event.target.matches?.("input, textarea, select")) return;
  const key = KEY_CODES[event.code] || event.key.toLowerCase();
  keys[key] = pressed;
  if (["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(key)) {
    event.preventDefault();
    sendInput(performance.now(), true);
  }
}
addEventListener("keydown", event => { updateKey(event, true); if (event.code === "Escape" || event.key === "Escape") { ws?.close(); location.reload(); } });
addEventListener("keyup", event => updateKey(event, false));
addEventListener("blur", () => { keys = {}; mouse.down = false; touchMove.x = 0; touchMove.y = 0; touchAim.active = false; sendInput(performance.now(), true); });
canvas.addEventListener("pointermove", event => {
  if (event.pointerType !== "touch") { mouse.x = event.clientX; mouse.y = event.clientY; }
});
canvas.addEventListener("pointerdown", event => {
  if (event.pointerType === "touch") { event.preventDefault(); return; }
  event.preventDefault(); mouse.x = event.clientX; mouse.y = event.clientY; mouse.down = true;
  canvas.setPointerCapture?.(event.pointerId);
});
function stopShooting(event) {
  if (event.pointerType !== "touch") mouse.down = false;
}
canvas.addEventListener("pointerup", stopShooting); canvas.addEventListener("pointercancel", stopShooting);
canvas.oncontextmenu = event => event.preventDefault();

function updateJoystick(event) {
  event.preventDefault();
  const rect = joystick.getBoundingClientRect(), centerX = rect.left + rect.width / 2, centerY = rect.top + rect.height / 2;
  let dx = event.clientX - centerX, dy = event.clientY - centerY;
  const maxDistance = rect.width * .34, distance = Math.hypot(dx, dy);
  if (distance > maxDistance) { dx = dx / distance * maxDistance; dy = dy / distance * maxDistance; }
  touchMove.x = dx / maxDistance; touchMove.y = dy / maxDistance;
  joystickKnob.style.left = `${rect.width / 2 + dx}px`; joystickKnob.style.top = `${rect.height / 2 + dy}px`;
  sendInput(performance.now());
}
function resetJoystick(event) {
  if (event.pointerId !== movePointer) return;
  touchMove.x = 0; touchMove.y = 0; movePointer = null;
  joystickKnob.style.left = "50%"; joystickKnob.style.top = "50%";
  sendInput(performance.now(), true);
}
joystick.addEventListener("pointerdown", event => {
  event.preventDefault(); movePointer = event.pointerId; joystick.setPointerCapture?.(event.pointerId); updateJoystick(event);
});
joystick.addEventListener("pointermove", event => { if (event.pointerId === movePointer) updateJoystick(event); });
joystick.addEventListener("pointerup", resetJoystick); joystick.addEventListener("pointercancel", resetJoystick);

function updateAimJoystick(event) {
  event.preventDefault();
  const rect = aimJoystick.getBoundingClientRect(), centerX = rect.left + rect.width / 2, centerY = rect.top + rect.height / 2;
  let dx = event.clientX - centerX, dy = event.clientY - centerY;
  const maxDistance = rect.width * .34, distance = Math.hypot(dx, dy);
  if (distance > 4) { touchAim.x = dx / distance; touchAim.y = dy / distance; }
  if (distance > maxDistance) { dx = dx / distance * maxDistance; dy = dy / distance * maxDistance; }
  aimJoystickKnob.style.left = `${rect.width / 2 + dx}px`; aimJoystickKnob.style.top = `${rect.height / 2 + dy}px`;
  sendInput(performance.now());
}
function resetAimJoystick(event) {
  if (event.pointerId !== aimPointer) return;
  touchAim.active = false; aimPointer = null;
  aimJoystickKnob.style.left = "50%"; aimJoystickKnob.style.top = "50%";
  sendInput(performance.now(), true);
}
aimJoystick.addEventListener("pointerdown", event => {
  event.preventDefault(); aimPointer = event.pointerId; touchAim.active = true;
  aimJoystick.setPointerCapture?.(event.pointerId); updateAimJoystick(event);
});
aimJoystick.addEventListener("pointermove", event => { if (event.pointerId === aimPointer) updateAimJoystick(event); });
aimJoystick.addEventListener("pointerup", resetAimJoystick); aimJoystick.addEventListener("pointercancel", resetAimJoystick);
addEventListener("pointerup", event => { resetJoystick(event); resetAimJoystick(event); });
addEventListener("pointercancel", event => { resetJoystick(event); resetAimJoystick(event); });
function sendInput(now = performance.now(), force = false) {
  if (!ws || ws.readyState !== WebSocket.OPEN || (!force && (now - lastSend < 33 || ws.bufferedAmount > 65536))) return; lastSend = now;
  const me = state.players.find(player => player.id === myId); if (!me) return;
  if (requestedMode === "profession" && me.ready !== true) return;
  const movement = currentMoveVector(), aimOrigin = predictedSelf || me, canvasRect = canvas.getBoundingClientRect();
  const screenX = canvasRect.left + (aimOrigin.x - camera.x) * viewScale, screenY = canvasRect.top + (aimOrigin.y - camera.y) * viewScale;
  const angle = touchAim.active ? Math.atan2(touchAim.y, touchAim.x) : Math.atan2(mouse.y - screenY, mouse.x - screenX);
  ws.send(JSON.stringify({ type: "input",
    up: keys.w || keys.arrowup || touchMove.y < -.18, down: keys.s || keys.arrowdown || touchMove.y > .18,
    left: keys.a || keys.arrowleft || touchMove.x < -.18, right: keys.d || keys.arrowright || touchMove.x > .18,
    move_x: movement.x, move_y: movement.y, stop_x: movement.moving ? undefined : aimOrigin.x,
    stop_y: movement.moving ? undefined : aimOrigin.y,
    shoot: mouse.down || touchAim.active, ability: Boolean(keys[" "]), angle }));
}
function visible(x, y, width = 0, height = 0, margin = 70) {
  return x + width >= camera.x - margin && x <= camera.x + sceneWidth + margin && y + height >= camera.y - margin && y <= camera.y + sceneHeight + margin;
}
function currentMoveVector() {
  let x = Number(Boolean(keys.d || keys.arrowright)) - Number(Boolean(keys.a || keys.arrowleft));
  let y = Number(Boolean(keys.s || keys.arrowdown)) - Number(Boolean(keys.w || keys.arrowup));
  let length = Math.hypot(x, y);
  if (length) return { x: x / length, y: y / length, moving: true };
  x = touchMove.x; y = touchMove.y; length = Math.hypot(x, y);
  if (length <= .12) return { x: 0, y: 0, moving: false };
  const strength = Math.min(1, (length - .12) / .88);
  return { x: x / length * strength, y: y / length * strength, moving: true };
}
function beginPredictionHold(now = performance.now()) {
  predictionWasMoving = false;
  const local = world.edition === "local" || world.edition === "offline";
  predictionHoldUntil = now + (local ? 55 : Math.min(180, Math.max(75, (latency ?? 140) * .5 + 30)));
}
function reconcilePrediction(me) {
  if (!me?.ready || me.hp <= 0) { predictedSelf = null; predictionWasMoving = false; predictionHoldUntil = 0; return; }
  const error = predictedSelf ? Math.hypot(predictedSelf.x - me.x, predictedSelf.y - me.y) : Infinity;
  if (!predictedSelf || error > 260) {
    predictedSelf = { x: me.x, y: me.y }; return;
  }
}
function predictedCircleHitsRect(x, y, radius, obstacle) {
  if (!obstacle.active) return false;
  const closestX = Math.max(obstacle.x, Math.min(x, obstacle.x + obstacle.w));
  const closestY = Math.max(obstacle.y, Math.min(y, obstacle.y + obstacle.h));
  return (x - closestX) ** 2 + (y - closestY) ** 2 < radius ** 2;
}
function updateLocalPrediction(now) {
  const dt = Math.min(Math.max(0, now - lastFrame) / 1000, .05); lastFrame = now;
  const me = state.players.find(player => player.id === myId);
  if (!me?.ready || me.hp <= 0) { predictedSelf = null; predictionWasMoving = false; predictionHoldUntil = 0; return; }
  if (!predictedSelf) predictedSelf = { x: me.x, y: me.y };
  const movement = currentMoveVector();
  const speed = 300 * (me.effects?.speed ? 1.45 : 1), radius = 25;
  predictionBlocked = false;
  if (movement.moving) {
    predictionWasMoving = true; predictionHoldUntil = 0;
    const nextX = Math.max(radius, Math.min(world.width - radius, predictedSelf.x + movement.x * speed * dt));
    if (!(state.obstacles || []).some(obstacle => predictedCircleHitsRect(nextX, predictedSelf.y, radius, obstacle))) predictedSelf.x = nextX; else predictionBlocked = true;
    const nextY = Math.max(radius, Math.min(world.height - radius, predictedSelf.y + movement.y * speed * dt));
    if (!(state.obstacles || []).some(obstacle => predictedCircleHitsRect(predictedSelf.x, nextY, radius, obstacle))) predictedSelf.y = nextY; else predictionBlocked = true;
  } else if (predictionWasMoving) beginPredictionHold(now);
  const serverMoving = Math.hypot(me.move_x || 0, me.move_y || 0) > .01;
  if (!movement.moving && (now < predictionHoldUntil || serverMoving)) return;
  const local = world.edition === "local" || world.edition === "offline", stateAge = Math.max(0, now - stateReceivedAt) / 1000;
  const baseLead = local ? 0 : Math.min(.14, Math.max(.035, (latency ?? 140) / 2000 + 1 / (world.network_rate || 25)));
  const lead = movement.moving ? (local ? 0 : Math.min(.19, baseLead + stateAge)) : 0;
  let targetX = me.x, targetY = me.y;
  const targetNextX = Math.max(radius, Math.min(world.width - radius, targetX + movement.x * speed * lead));
  if (!(state.obstacles || []).some(obstacle => predictedCircleHitsRect(targetNextX, targetY, radius, obstacle))) targetX = targetNextX;
  const targetNextY = Math.max(radius, Math.min(world.height - radius, targetY + movement.y * speed * lead));
  if (!(state.obstacles || []).some(obstacle => predictedCircleHitsRect(targetX, targetNextY, radius, obstacle))) targetY = targetNextY;
  const errorX = targetX - predictedSelf.x, errorY = targetY - predictedSelf.y, error = Math.hypot(errorX, errorY);
  if (error > 260) { predictedSelf.x = targetX; predictedSelf.y = targetY; return; }
  if (error < .15) return;
  const alpha = 1 - Math.exp(-(local ? 11 : predictionBlocked ? 12 : 7) * dt);
  const maxStep = (local ? 440 : predictionBlocked ? 440 : 300) * dt, step = Math.min(error * alpha, maxStep);
  predictedSelf.x += errorX / error * step; predictedSelf.y += errorY / error * step;
}
function updateLatency(now) {
  if (!ws || ws.readyState !== WebSocket.OPEN || now - lastPing < 2000) return;
  lastPing = now; ws.send(JSON.stringify({ type: "ping", sent: now }));
}
function smoothPoint(key, x, y) {
  let point = smoothPositions.get(key);
  if (!point || Math.hypot(point.x - x, point.y - y) > 420) point = { x, y };
  point.x += (x - point.x) * .38; point.y += (y - point.y) * .38;
  smoothPositions.set(key, point); return point;
}
function smoothedPlayers() {
  const seen = new Set();
  const players = state.players.map(player => {
    const playerKey = `p${player.id}`;
    const point = player.id === myId && predictedSelf && player.ready ? predictedSelf : smoothPoint(playerKey, player.x, player.y);
    if (point !== predictedSelf) seen.add(playerKey);
    const minions = (player.minions || []).map(minion => {
      const key = `m${player.id}:${minion.id}`, minionPoint = smoothPoint(key, minion.x, minion.y); seen.add(key);
      return { ...minion, x: minionPoint.x, y: minionPoint.y };
    });
    return { ...player, x: point.x, y: point.y, minions };
  });
  for (const key of smoothPositions.keys()) if (!seen.has(key)) smoothPositions.delete(key);
  return players;
}
function drawGrid() {
  ctx.fillStyle = "#080d1b"; ctx.fillRect(0, 0, sceneWidth, sceneHeight); ctx.strokeStyle = "#172540"; ctx.lineWidth = 1; const size = 80;
  for (let x = -camera.x % size; x < sceneWidth; x += size) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, sceneHeight); ctx.stroke(); }
  for (let y = -camera.y % size; y < sceneHeight; y += size) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(sceneWidth, y); ctx.stroke(); }
  ctx.strokeStyle = "#42618f"; ctx.lineWidth = 4; ctx.strokeRect(-camera.x, -camera.y, world.width, world.height);
}
function drawObstacle(o) {
  if (!visible(o.x, o.y, o.w, o.h, 20)) return;
  const x = o.x - camera.x, y = o.y - camera.y, gradient = ctx.createLinearGradient(x, y, x, y + o.h);
  if (!o.active) {
    ctx.save(); ctx.globalAlpha = .32; ctx.strokeStyle = "#607da8"; ctx.lineWidth = 1; ctx.setLineDash([4, 5]);
    ctx.strokeRect(x + 2, y + 2, o.w - 4, o.h - 4); ctx.setLineDash([]);
    ctx.fillStyle = "#b8cff1"; ctx.font = "10px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(Math.ceil(o.restore), x + o.w / 2, y + o.h / 2); ctx.restore(); return;
  }
  gradient.addColorStop(0, "#314665"); gradient.addColorStop(1, "#17243b"); ctx.fillStyle = gradient; ctx.strokeStyle = "#607da8"; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.roundRect(x, y, o.w, o.h, 9); ctx.fill(); ctx.stroke(); ctx.strokeStyle = "#233653"; ctx.lineWidth = 2;
  for (let offset = 20; offset < o.w; offset += 38) { ctx.beginPath(); ctx.moveTo(x + offset, y + 4); ctx.lineTo(x + offset - 14, y + o.h - 4); ctx.stroke(); }
}
function drawMinions(players) {
  for (const owner of players) for (const minion of owner.minions || []) {
    if (!visible(minion.x, minion.y)) continue;
    const x = minion.x - camera.x, y = minion.y - camera.y;
    ctx.save(); ctx.shadowBlur = 13; ctx.shadowColor = owner.color; ctx.fillStyle = "#0c1629"; ctx.strokeStyle = owner.color; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(x, y, 11, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); ctx.shadowBlur = 0;
    ctx.fillStyle = owner.color; ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#142039"; ctx.fillRect(x - 12, y + 16, 24, 3); ctx.fillStyle = "#72f1d0"; ctx.fillRect(x - 12, y + 16, 24 * Math.max(0, minion.hp) / (minion.max_hp || 100 / 3), 3); ctx.restore();
  }
}
function drawPickup(p, now) {
  if (!visible(p.x, p.y)) return;
  const data = POWERUPS[p.kind], x = p.x - camera.x, y = p.y - camera.y, pulse = 1 + Math.sin(now / 180 + p.id) * .1;
  ctx.save(); ctx.shadowBlur = mobileMode ? 10 : 28; ctx.shadowColor = data.color; ctx.fillStyle = data.color; ctx.globalAlpha = .25; ctx.beginPath(); ctx.arc(x, y, 29 * pulse, 0, Math.PI * 2); ctx.fill();
  ctx.globalAlpha = 1; ctx.fillStyle = "#10192d"; ctx.strokeStyle = data.color; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, 20, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  ctx.shadowBlur = 0; ctx.fillStyle = data.color; ctx.font = "bold 22px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(data.icon, x, y + 1);
  ctx.fillStyle = "#dbe8ff"; ctx.font = "bold 11px sans-serif"; ctx.fillText(data.name, x, y + 37); ctx.restore();
}
function drawPlayer(p) {
  if (!p.ready) return;
  if (!visible(p.x, p.y)) return;
  const x = p.x - camera.x, y = p.y - camera.y, dead = p.hp <= 0; ctx.save(); ctx.globalAlpha = dead ? .22 : 1;
  if (p.effects?.shield) { ctx.fillStyle = "#55e6ff22"; ctx.strokeStyle = "#55e6ff"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, 34, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); }
  if (p.effects?.invincible) { ctx.fillStyle = "#ffe17a2a"; ctx.strokeStyle = "#ffe17a"; ctx.lineWidth = 5; ctx.shadowBlur = mobileMode ? 10 : 25; ctx.shadowColor = "#ffe17a"; ctx.beginPath(); ctx.arc(x, y, 38, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); ctx.shadowBlur = 0; }
  ctx.shadowBlur = mobileMode ? 9 : 22; ctx.shadowColor = p.color; ctx.fillStyle = p.color; ctx.beginPath(); ctx.arc(x, y, 24, 0, Math.PI * 2); ctx.fill();
  ctx.shadowBlur = 0; ctx.strokeStyle = "#fff"; ctx.lineWidth = p.id === myId ? 4 : 2; ctx.stroke();
  if (Object.keys(p.effects || {}).length) { ctx.strokeStyle = "#ffd166"; ctx.lineWidth = 2; ctx.setLineDash([4, 5]); ctx.beginPath(); ctx.arc(x, y, 31, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]); }
  ctx.fillStyle = "#eaf2ff"; ctx.font = "bold 13px sans-serif"; ctx.textAlign = "center"; ctx.fillText(dead ? "复活中…" : p.name, x, y - 40);
  ctx.fillStyle = "#17213b"; ctx.fillRect(x - 26, y + 33, 52, 6); ctx.fillStyle = p.hp > p.max_hp / 2 ? "#55d6be" : "#ff5d73"; ctx.fillRect(x - 26, y + 33, 52 * Math.max(0, p.hp) / p.max_hp, 6); ctx.restore();
}
function recordSpeedTrails(players) {
  for (const p of players) {
    if (!p.effects?.speed || p.hp <= 0) continue;
    const trail = speedTrails.get(p.id) || [], last = trail.at(-1);
    if (!last || Math.hypot(p.x - last.x, p.y - last.y) >= 8) {
      trail.push({ x: p.x, y: p.y, color: p.color, alpha: .5 });
      if (trail.length > 10) trail.shift();
      speedTrails.set(p.id, trail);
    }
  }
}
function drawSpeedTrails() {
  for (const [id, trail] of speedTrails) {
    for (const ghost of trail) {
      if (!visible(ghost.x, ghost.y)) { ghost.alpha -= .022; continue; }
      ctx.save(); ctx.globalAlpha = ghost.alpha; ctx.fillStyle = ghost.color; ctx.shadowBlur = mobileMode ? 5 : 14; ctx.shadowColor = ghost.color;
      ctx.beginPath(); ctx.arc(ghost.x - camera.x, ghost.y - camera.y, 22, 0, Math.PI * 2); ctx.fill(); ctx.restore();
      ghost.alpha -= .022;
    }
    const remainingTrail = trail.filter(ghost => ghost.alpha > 0);
    if (remainingTrail.length) speedTrails.set(id, remainingTrail); else speedTrails.delete(id);
  }
}
function extrapolatedBulletPosition(bullet, seconds) {
  const radius = bullet.radius || 6, dx = (bullet.vx || 0) * seconds, dy = (bullet.vy || 0) * seconds;
  let fraction = 1;
  const clipAxis = (start, delta, lower, upper) => {
    if (delta > 0) fraction = Math.min(fraction, (upper - start) / delta);
    else if (delta < 0) fraction = Math.min(fraction, (lower - start) / delta);
  };
  clipAxis(bullet.x, dx, radius, world.width - radius);
  clipAxis(bullet.y, dy, radius, world.height - radius);
  for (const obstacle of state.obstacles || []) {
    if (!obstacle.active) continue;
    const left = obstacle.x - radius, right = obstacle.x + obstacle.w + radius;
    const top = obstacle.y - radius, bottom = obstacle.y + obstacle.h + radius;
    let enter = -Infinity, exit = Infinity;
    for (const [start, delta, lower, upper] of [[bullet.x, dx, left, right], [bullet.y, dy, top, bottom]]) {
      if (Math.abs(delta) < .0001) { if (start < lower || start > upper) { enter = Infinity; break; } continue; }
      const a = (lower - start) / delta, b = (upper - start) / delta;
      enter = Math.max(enter, Math.min(a, b)); exit = Math.min(exit, Math.max(a, b));
    }
    if (enter <= exit && exit >= 0 && enter >= .0001 && enter <= 1) fraction = Math.min(fraction, Math.max(0, enter - .002));
  }
  fraction = Math.max(0, Math.min(1, fraction));
  return { x: bullet.x + dx * fraction, y: bullet.y + dy * fraction };
}
function drawProjectiles(now) {
  const extrapolation = Math.min(Math.max(0, now - stateReceivedAt) / 1000, .06);
  for (const l of state.lasers || []) { let laserX1 = l.x1, laserY1 = l.y1; if (l.owner === myId && l.segment === 0 && predictedSelf && (l.age || 0) < .18) { const blend = 1 - (l.age || 0) / .18; laserX1 += (predictedSelf.x - l.x1) * blend; laserY1 += (predictedSelf.y - l.y1) * blend; } if (!visible(Math.min(laserX1, l.x2), Math.min(laserY1, l.y2), Math.abs(l.x2 - laserX1), Math.abs(l.y2 - laserY1))) continue; ctx.save(); ctx.strokeStyle = l.color; ctx.shadowColor = l.color; ctx.shadowBlur = mobileMode ? 8 : l.beam ? 17 : 25; ctx.lineWidth = l.beam ? 7 : 11; ctx.globalAlpha = l.beam ? .18 : .25; ctx.beginPath(); ctx.moveTo(laserX1 - camera.x, laserY1 - camera.y); ctx.lineTo(l.x2 - camera.x, l.y2 - camera.y); ctx.stroke(); ctx.lineWidth = l.beam ? 2.5 : 4; ctx.globalAlpha = 1; ctx.beginPath(); ctx.moveTo(laserX1 - camera.x, laserY1 - camera.y); ctx.lineTo(l.x2 - camera.x, l.y2 - camera.y); ctx.stroke(); ctx.restore(); }
  for (const b of state.bullets || []) { let visualBullet = b; if (b.owner === myId && predictedSelf && (b.age || 0) < .18) { const serverMe = state.players.find(player => player.id === myId), blend = 1 - (b.age || 0) / .18; if (serverMe) visualBullet = { ...b, x: b.x + (predictedSelf.x - serverMe.x) * blend, y: b.y + (predictedSelf.y - serverMe.y) * blend }; } const predicted = extrapolatedBulletPosition(visualBullet, extrapolation), bulletX = predicted.x, bulletY = predicted.y; if (!visible(bulletX, bulletY)) continue; const radius = b.radius || 6; ctx.fillStyle = b.color; ctx.shadowBlur = mobileMode ? 7 : b.kind === "cannon" ? 28 : 16; ctx.shadowColor = b.color; ctx.beginPath(); ctx.arc(bulletX - camera.x, bulletY - camera.y, radius, 0, Math.PI * 2); ctx.fill(); if (b.kind === "cannon") { ctx.strokeStyle = "#ffe2a8"; ctx.lineWidth = 4; ctx.stroke(); } else if (b.kind === "mage") { ctx.strokeStyle = "#fff"; ctx.lineWidth = 3; ctx.stroke(); } else if (b.kind === "sniper") { ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(bulletX - camera.x, bulletY - camera.y, 2, 0, Math.PI * 2); ctx.fill(); } else if (b.bounces > 0) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke(); } } ctx.shadowBlur = 0;
  for (const blast of state.explosions || []) { if (!visible(blast.x, blast.y, 0, 0, blast.radius)) continue; const total = blast.magic ? .25 : .35, alpha = Math.max(0, blast.life / total), radius = blast.radius * (1 - alpha * .45); ctx.save(); ctx.globalAlpha = alpha; ctx.fillStyle = `${blast.color}44`; ctx.strokeStyle = blast.magic ? "#f6e8ff" : blast.color; ctx.lineWidth = blast.magic ? 4 : 7; ctx.shadowBlur = mobileMode ? 10 : 30; ctx.shadowColor = blast.color; ctx.beginPath(); ctx.arc(blast.x - camera.x, blast.y - camera.y, radius, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); ctx.restore(); }
}
function render(now) {
  updateLocalPrediction(now); updateLatency(now);
  const displayPlayers = smoothedPlayers(), me = displayPlayers.find(player => player.id === myId);
  if (me) { camera.x += (me.x - sceneWidth / 2 - camera.x) * .12; camera.y += (me.y - sceneHeight / 2 - camera.y) * .12; camera.x = Math.max(0, Math.min(world.width - sceneWidth, camera.x)); camera.y = Math.max(0, Math.min(world.height - sceneHeight, camera.y)); }
  ctx.save(); ctx.scale(viewScale, viewScale);
  drawGrid(); (state.pickups || []).forEach(p => drawPickup(p, now)); (state.obstacles || []).forEach(drawObstacle); drawSpeedTrails(); drawProjectiles(now); drawMinions(displayPlayers); displayPlayers.forEach(drawPlayer);
  ctx.restore();
  const board = [...state.players].sort((a, b) => b.score - a.score); ctx.textAlign = "right"; ctx.font = "bold 14px sans-serif";
  board.forEach((p, i) => { ctx.fillStyle = p.id === myId ? "#72f1d0" : "#c5d1e6"; ctx.fillText(`${i + 1}. ${p.name}  ${p.score}`, viewWidth - 20, 32 + i * 22); });
  if (myId && !receivedState) { ctx.fillStyle = "#eef6ff"; ctx.font = "bold 20px sans-serif"; ctx.textAlign = "center"; ctx.fillText("正在等待服务器状态…", viewWidth / 2, viewHeight / 2); }
  sendInput(now); requestAnimationFrame(render);
}
requestAnimationFrame(render);
