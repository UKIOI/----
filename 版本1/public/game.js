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
const rescueToggle = document.querySelector("#rescueToggle");
const testToggle = document.querySelector("#testToggle");
const testPanel = document.querySelector("#testPanel");
const testClose = document.querySelector("#testClose");
const testApply = document.querySelector("#testApply");
const testInfectSelf = document.querySelector("#testInfectSelf");
const zombieSelect = document.querySelector("#zombieSelect");
const zombieLives = document.querySelector("#zombieLives");
const autoAimToggle = document.querySelector("#autoAimToggle");
const chatToggle = document.querySelector("#chatToggle");
const chatUnread = document.querySelector("#chatUnread");
const chatPanel = document.querySelector("#chatPanel");
const chatClose = document.querySelector("#chatClose");
const chatMessages = document.querySelector("#chatMessages");
const chatForm = document.querySelector("#chatForm");
const chatInput = document.querySelector("#chatInput");
const soundToggle = document.querySelector("#soundToggle");
const roomBrowser = document.querySelector("#roomBrowser");
const roomBrowserToggle = document.querySelector("#roomBrowserToggle");
const roomBrowserClose = document.querySelector("#roomBrowserClose");
const roomList = document.querySelector("#roomList");
const roomRefresh = document.querySelector("#roomRefresh");
const guidePanel = document.querySelector("#guidePanel");
const guideToggle = document.querySelector("#guideToggle");
const guideClose = document.querySelector("#guideClose");
const upgradePanel = document.querySelector("#upgrades");
const upgradeProgress = document.querySelector("#upgradeProgress");
const upgradeChoices = document.querySelector("#upgradeChoices");
const MODE_NAMES = { classic: "经典模式", items: "多道具模式", pure: "纯净模式", profession: "职业模式", upgrade: "升级模式", bio: "生化模式" };
const ROLE_NAMES = { tank: "坦克", mage: "法师", sniper: "狙击手", necromancer: "死灵法师", weaponmaster: "武器大师", paladin: "圣骑士" };
const ZOMBIE_FORM_NAMES = { normal: "普通", raider: "突袭者", shooter: "射手", giant: "巨型", vomiter: "呕吐者", plague_lord: "瘟疫领主", brood_queen: "巢群女王", iron_abomination: "钢铁畸变体" };
const INFECTED_SKILLS = { normal: "狂暴", raider: "突袭", shooter: "毒弹齐射", giant: "震地", vomiter: "污染喷吐", plague_lord: "瘟疫领域", brood_queen: "召唤尸潮", iron_abomination: "毁灭冲锋" };
const INFECTED_MOVE_SPEEDS = { normal: 285, raider: 390, shooter: 270, giant: 185, vomiter: 235, plague_lord: 158.4, brood_queen: 187, iron_abomination: 136.4 };
const UPGRADE_INFO = {
  vitality: { icon: "♥", name: "生命强化", text: "最大生命 +15，并恢复 15 点", max: 3 },
  power: { icon: "◆", name: "火力强化", text: "子弹伤害 +10%", max: 3 },
  haste: { icon: "⚡", name: "快速装填", text: "射击间隔缩短 10%", max: 3 },
  agility: { icon: "➤", name: "机动强化", text: "移动速度 +6%", max: 3 },
  velocity: { icon: "»", name: "高速弹药", text: "子弹速度 +10%", max: 3 },
  arsenal: { icon: "✦", name: "武器扩展", text: "解锁双发，之后升级为三发", max: 2 },
};
const POWERUPS = {
  damage: { icon: "⚔", name: "强化伤害", color: "#ff5d73" }, rapid: { icon: "⚡", name: "高速射击", color: "#ffd166" },
  multishot: { icon: "✦", name: "三重子弹", color: "#64a8ff" }, laser: { icon: "▰", name: "半血激光", color: "#c77dff" },
  shield: { icon: "⬡", name: "强化护盾", color: "#55e6ff" }, speed: { icon: "➤", name: "移动加速", color: "#77ff88" },
  beam: { icon: "≋", name: "高能光束", color: "#ff72e1" },
  health: { icon: "+", name: "生命补给", color: "#ff4268" }, ricochet: { icon: "↗", name: "反弹弹药", color: "#ff9f43" },
  cannon: { icon: "●", name: "攻城大炮", color: "#ff7b39" }, minion: { icon: "◉", name: "战斗随从", color: "#72f1d0" },
  invincible: { icon: "✧", name: "神圣无敌", color: "#ffe17a" },
  infected_frenzy: { icon: "☣", name: "感染狂暴", color: "#9cff57" },
};
const PROTOCOL_VERSION = 16;
const BUILD_VERSION = 72;
const INPUT_INTERVAL_MS = 33;
let ws, myId = null, requestedMode = "classic", world = { width: 1600, height: 900 };
let state = { players: [], bullets: [], lasers: [], explosions: [], pickups: [], obstacles: [], zombies: [], hazards: [], bio: null };
let keys = {}, mouse = { x: 0, y: 0, down: false }, touchMove = { x: 0, y: 0 }, touchAim = { x: 1, y: 0, active: false };
let movePointer = null, aimPointer = null;
let autoAimEnabled = false, autoFirePointer = null, touchAutoShoot = false;
const mobileUserAgent = navigator.userAgentData?.mobile === true || /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|HarmonyOS|Mobile/i.test(navigator.userAgent);
const ipadLike = navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
const mobileMode = mobileUserAgent || ipadLike;
document.documentElement.classList.toggle("mobile-controls", mobileMode);
// 手机端缩小世界画面约 8%，同时展示更多地图区域。
let viewScale = mobileMode ? (innerHeight > innerWidth ? .57 : .66) : 1;
let camera = { x: 0, y: 0 }, lastSend = 0, receivedState = false, stateReceivedAt = performance.now();
let unreadChats = 0;
let predictedSelf = null, lastFrame = performance.now(), frameDeltaSeconds = 1 / 60, lastPing = 0, latency = null;
let predictionBlocked = false, inputSequence = 0, lastStopSequence = -1, lastSentMoving = false;
let viewWidth = innerWidth, viewHeight = innerHeight, sceneWidth = innerWidth / viewScale, sceneHeight = innerHeight / viewScale;
const speedTrails = new Map();
const speedTrailAnchors = new Map();
const motionTracks = new Map();
const REMOTE_INTERPOLATION_MS = 140;
const REMOTE_EXTRAPOLATION_MS = 80;
const BULLET_EXTRAPOLATION_MS = 220;
let serverClockOffset = null;
let audioContext = null, soundSnapshotReady = false;
let soundEnabled = (() => { try { return localStorage.getItem("neon-sound") !== "off"; } catch { return true; } })();
const soundCooldowns = new Map(), heardExplosions = new Map();
let roomRefreshTimer = 0;
let lastUpgradeSignature = "";
const exploredBioCells = new Set();
const bioTerrainCache = document.createElement("canvas");
let bioTerrainSignature = "";
function resize() {
  const viewport = window.visualViewport;
  const ratio = Math.min(devicePixelRatio || 1, mobileMode ? 1.5 : 2);
  viewWidth = Math.round(viewport?.width || innerWidth); viewHeight = Math.round(viewport?.height || innerHeight);
  viewScale = mobileMode ? (viewHeight > viewWidth ? .57 : .66) : 1;
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
function closeRoomBrowser() {
  roomBrowser.hidden = true; clearTimeout(roomRefreshTimer); roomRefreshTimer = 0;
}
async function refreshRoomBrowser() {
  clearTimeout(roomRefreshTimer); roomRefresh.disabled = true; roomRefresh.textContent = "刷新中…";
  try {
    const response = await fetch("/rooms", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json(); roomList.replaceChildren();
    if (!data.rooms?.length) {
      const empty = document.createElement("p"); empty.className = "room-empty"; empty.textContent = "目前还没有房间，可以创建第一个房间"; roomList.append(empty);
    } else for (const room of data.rooms) {
      const row = document.createElement("article"), code = document.createElement("b"), mode = document.createElement("span"), count = document.createElement("span"), choose = document.createElement("button");
      row.className = "room-row"; code.className = "room-code"; mode.className = "room-mode"; count.className = "room-count";
      code.textContent = room.code; mode.textContent = MODE_NAMES[room.mode] || room.mode;
      count.textContent = `${room.players}/${room.capacity} 真人${room.infected ? ` · ${room.infected} 感染` : ""}${room.bots ? ` · ${room.bots} 人机` : ""}`;
      choose.type = "button"; choose.disabled = room.players >= room.capacity; choose.textContent = choose.disabled ? "已满" : "选择";
      choose.addEventListener("click", () => {
        document.querySelector("#room").value = room.code; document.querySelector("#mode").value = room.mode;
        playEffect("ui"); closeRoomBrowser();
      });
      row.append(code, mode, count, choose); roomList.append(row);
    }
  } catch {
    roomList.replaceChildren(); const failed = document.createElement("p"); failed.className = "room-empty"; failed.textContent = "房间列表读取失败，请检查服务器连接后重试"; roomList.append(failed);
  } finally {
    roomRefresh.disabled = false; roomRefresh.textContent = "刷新列表";
    if (!roomBrowser.hidden) roomRefreshTimer = setTimeout(refreshRoomBrowser, 3000);
  }
}
function openRoomBrowser() {
  playEffect("ui"); roomBrowser.hidden = false; refreshRoomBrowser();
}
roomBrowserToggle.addEventListener("click", openRoomBrowser);
roomBrowserClose.addEventListener("click", () => { playEffect("ui"); closeRoomBrowser(); });
roomRefresh.addEventListener("click", refreshRoomBrowser);
roomBrowser.addEventListener("click", event => { if (event.target === roomBrowser) closeRoomBrowser(); });
function closeGuide() { guidePanel.hidden = true; }
function openGuide() { playEffect("ui"); guidePanel.hidden = false; }
guideToggle.addEventListener("click", openGuide);
guideClose.addEventListener("click", () => { playEffect("ui"); closeGuide(); });
guidePanel.addEventListener("click", event => { if (event.target === guidePanel) closeGuide(); });
function connect() {
  ensureAudio(); playEffect("ui");
  document.querySelector("#join").disabled = true;
  requestedMode = document.querySelector("#mode").value;
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  statusLabel.textContent = "连接中…";
  ws.onopen = () => ws.send(JSON.stringify({ type: "join", name: document.querySelector("#name").value, room: document.querySelector("#room").value, mode: document.querySelector("#mode").value }));
  ws.onmessage = event => {
    const data = JSON.parse(event.data);
    if (data.type === "welcome") {
      if (data.protocol !== PROTOCOL_VERSION) {
        const refreshKey = `neon-protocol-refresh-${data.protocol}`, lastRefresh = Number(sessionStorage.getItem(refreshKey) || 0);
        ws.close();
        if (Date.now() - lastRefresh > 15000) {
          sessionStorage.setItem(refreshKey, String(Date.now()));
          const freshUrl = new URL(location.href); freshUrl.searchParams.set("refresh", String(Date.now())); location.replace(freshUrl);
        } else alert("客户端仍未更新，请关闭全部游戏页面后重新打开");
        return;
      }
      if (data.build !== BUILD_VERSION) {
        alert("主机仍在运行旧版服务器，请主机关闭原启动窗口，然后重新运行 start_internet.bat");
        ws.close();
        return;
      }
      if (data.mode !== requestedMode) {
        alert("该房间已使用其他玩法模式，请返回房间列表重新选择"); ws.close(); return;
      }
      myId = data.id; world = data; state.obstacles = data.obstacles || []; predictedSelf = null; motionTracks.clear(); speedTrails.clear(); speedTrailAnchors.clear(); heardExplosions.clear(); exploredBioCells.clear(); soundSnapshotReady = false; serverClockOffset = null; inputSequence = 0; lastStopSequence = -1; lastSentMoving = false; lastPing = 0; menu.hidden = true; game.hidden = false; canvas.tabIndex = 0; canvas.focus();
      document.querySelector("#roomLabel").textContent = `房间 ${data.room} · ${MODE_NAMES[data.mode]}`;
      statusLabel.textContent = data.mode === "profession" ? "请选择职业" : "正在载入战场…";
      rolePanel.hidden = data.mode !== "profession"; upgradePanel.hidden = true; zombieSelect.hidden = true; testPanel.hidden = true; lastUpgradeSignature = "";
      autoAimToggle.hidden = !mobileMode;
    } else if (data.type === "state") {
      const receivedAt = performance.now(), destroyed = new Map(data.destroyed || []);
      data.obstacles = (state.obstacles || []).map(obstacle => ({ ...obstacle, active: !destroyed.has(obstacle.id), restore: destroyed.get(obstacle.id) || 0 }));
      reconcilePrediction(data.players.find(player => player.id === myId));
      recordMotionSnapshots(data, synchronizedSnapshotTime(data.server_time, receivedAt)); playStateSounds(state, data, receivedAt); state = data; stateReceivedAt = receivedAt; receivedState = true; const me = data.players.find(player => player.id === myId);
      if (requestedMode === "profession") rolePanel.hidden = me?.ready === true;
      const isBioHost = requestedMode === "bio" && data.bio?.host_id === myId;
      rescueToggle.hidden = !isBioHost; rescueToggle.disabled = false;
      rescueToggle.classList.toggle("enabled", Boolean(data.bio?.rescue_enabled));
      rescueToggle.textContent = data.bio?.rescue_enabled ? "救援：已开启" : "救援：关闭";
      testToggle.hidden = data.host_id !== myId;
      testInfectSelf.hidden = requestedMode !== "bio" || data.host_id !== myId || Boolean(me?.infected);
      updateZombiePanel(me, data.bio);
      updateUpgradePanel(me);
      const isPaladin = me?.ready && me.role === "paladin" && me.hp > 0;
      const isInfected = requestedMode === "bio" && me?.ready && me.infected && !me.choosing_zombie && me.hp > 0;
      const skillName = isInfected ? INFECTED_SKILLS[me.zombie_form] || "感染技能" : "圣盾";
      skillButton.hidden = !(isPaladin || isInfected);
      if (isPaladin || isInfected) { skillButton.disabled = me.ability_cooldown > 0; skillButton.textContent = me.ability_cooldown > 0 ? `${skillName} ${Math.ceil(me.ability_cooldown)}s` : skillName; }
      const pingText = latency === null ? "" : ` · ${latency}ms`;
      const levelText = ["upgrade", "bio"].includes(requestedMode) && me ? ` · Lv.${me.level} 经验 ${me.xp}/${me.next_level_score ?? "满级"}` : "";
      const deadStatus = me?.infected ? me.choosing_zombie ? `选择感染形态 · 本波还可复活 ${me.zombie_respawns} 次` : "感染体复活次数已耗尽" : me?.infection_progress ? `尸体感染中 ${me.infection_progress.toFixed(1)}/5秒` : data.bio?.rescue_enabled ? `你已阵亡 · 等待队友救援${me?.rescue_progress ? ` ${me.rescue_progress.toFixed(1)}/10秒` : ""}` : "你已阵亡 · 本局无法复活";
      statusLabel.textContent = me && !me.ready ? "请选择职业" : requestedMode === "bio" && me?.hp <= 0 ? deadStatus : me?.upgrading ? "升级选择中 · 当前无敌" : `${me?.role ? ROLE_NAMES[me.role] + " · " : ""}已连接 · ${data.players.length} 人在线${levelText}${pingText}`; updatePowerLabel();
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
  playEffect("ui");
  ws?.send(JSON.stringify({ type: "select_role", role: button.dataset.role }));
  statusLabel.textContent = "正在进入战场…";
});
skillButton.addEventListener("pointerdown", event => {
  event.preventDefault();
  if (!skillButton.disabled) { playEffect("shield"); ws?.send(JSON.stringify({ type: "ability" })); }
});
rescueToggle.addEventListener("click", () => {
  if (requestedMode !== "bio" || rescueToggle.hidden) return;
  playEffect("ui"); rescueToggle.disabled = true;
  ws?.send(JSON.stringify({ type: "toggle_rescue", enabled: !state.bio?.rescue_enabled }));
});
function updateZombiePanel(me, bio) {
  const choosing = requestedMode === "bio" && me?.infected && me?.choosing_zombie;
  const wasHidden = zombieSelect.hidden;
  zombieSelect.hidden = !choosing;
  if (!choosing) return;
  zombieLives.textContent = `本波剩余复活机会：${me.zombie_respawns}`;
  const bossAllowed = bio?.wave > 0 && bio.wave % 5 === 0 && me.boss_used_wave !== bio.wave;
  document.querySelectorAll("[data-zombie-boss]").forEach(button => { button.disabled = !bossAllowed; });
  if (wasHidden) stopGameInput();
}
document.querySelectorAll("[data-zombie], [data-zombie-boss]").forEach(button => button.addEventListener("click", () => {
  playEffect("ui"); ws?.send(JSON.stringify({ type: "select_zombie", form: button.dataset.zombie || button.dataset.zombieBoss }));
}));
function syncTestInputs() {
  for (const input of document.querySelectorAll("[data-test]")) input.value = state.test?.[input.dataset.test] ?? "";
}
testToggle.addEventListener("click", () => { playEffect("ui"); syncTestInputs(); testPanel.hidden = false; stopGameInput(); });
testClose.addEventListener("click", () => { testPanel.hidden = true; });
testApply.addEventListener("click", () => {
  const values = {}; for (const input of document.querySelectorAll("[data-test]")) values[input.dataset.test] = Number(input.value);
  ws?.send(JSON.stringify({ type: "test_settings", values })); playEffect("ui"); testPanel.hidden = true;
});
testInfectSelf.addEventListener("click", () => {
  if (requestedMode !== "bio" || state.host_id !== myId) return;
  ws?.send(JSON.stringify({ type: "test_infect_self" })); playEffect("hurt"); testPanel.hidden = true;
});
autoAimToggle.addEventListener("click", () => {
  autoAimEnabled = !autoAimEnabled; document.documentElement.classList.toggle("auto-aim", autoAimEnabled);
  autoAimToggle.classList.toggle("enabled", autoAimEnabled); autoAimToggle.textContent = `自动瞄准：${autoAimEnabled ? "开" : "关"}`;
  touchAim.active = false; aimPointer = null; touchAutoShoot = false; sendInput(performance.now(), true);
});
function updateUpgradePanel(me) {
  const choices = ["upgrade", "bio"].includes(requestedMode) ? me?.upgrade_choices || [] : [];
  if (!choices.length) { upgradePanel.hidden = true; lastUpgradeSignature = ""; return; }
  const signature = `${me.level}:${choices.join(",")}`;
  if (signature === lastUpgradeSignature) return;
  const wasHidden = upgradePanel.hidden; lastUpgradeSignature = signature; upgradeChoices.replaceChildren();
  upgradeProgress.textContent = `已升至 Lv.${me.level}，选择一项永久强化`;
  for (const kind of choices) {
    const info = UPGRADE_INFO[kind], rank = me.upgrades?.[kind] || 0, button = document.createElement("button");
    const title = document.createElement("b"), detail = document.createElement("small"), level = document.createElement("em"), unlimited = requestedMode === "bio" && kind !== "arsenal";
    title.textContent = `${info.icon} ${info.name}`; detail.textContent = info.text; level.textContent = unlimited ? `当前 ${rank} → ${rank + 1}（无限）` : `当前 ${rank}/${info.max} → ${rank + 1}/${info.max}`;
    button.append(title, detail, level);
    button.addEventListener("click", () => { playEffect("pickup"); button.disabled = true; ws?.send(JSON.stringify({ type: "select_upgrade", upgrade: kind })); upgradePanel.hidden = true; });
    upgradeChoices.append(button);
  }
  upgradePanel.hidden = false;
  if (wasHidden) stopGameInput();
}
function stopGameInput() {
  keys = {}; mouse.down = false; touchMove.x = 0; touchMove.y = 0; touchAim.active = false; touchAutoShoot = false;
  movePointer = null; aimPointer = null; autoFirePointer = null;
  joystickKnob.style.left = "50%"; joystickKnob.style.top = "50%";
  aimJoystickKnob.style.left = "50%"; aimJoystickKnob.style.top = "50%";
  sendInput(performance.now(), true);
}
function openChat() {
  playEffect("ui"); chatPanel.hidden = false; chatToggle.hidden = true; unreadChats = 0; chatUnread.hidden = true; chatUnread.textContent = "0"; chatToggle.setAttribute("aria-label", "打开聊天");
  stopGameInput(); setTimeout(() => chatInput.focus(), 0);
}
function closeChatPanel() {
  playEffect("ui"); chatPanel.hidden = true; chatToggle.hidden = false; chatInput.blur(); canvas.focus({ preventScroll: true });
}
function appendChatMessage(data) {
  chatMessages.querySelector(".chat-tip")?.remove();
  const line = document.createElement("p"), name = document.createElement("b"), message = document.createElement("span");
  line.className = "chat-message"; name.textContent = `${data.level ? `[Lv.${data.level}] ` : ""}${data.name}:`; name.style.color = data.color; message.textContent = data.message;
  line.append(name, message); chatMessages.append(line);
  while (chatMessages.children.length > 60) chatMessages.firstElementChild.remove();
  chatMessages.scrollTop = chatMessages.scrollHeight;
  if (chatPanel.hidden) { unreadChats += 1; chatUnread.textContent = unreadChats > 9 ? "9+" : String(unreadChats); chatUnread.hidden = false; chatUnread.title = `${unreadChats} 条未读消息`; chatToggle.setAttribute("aria-label", `打开聊天，${unreadChats} 条未读消息`); playEffect("chat"); }
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
function ensureAudio() {
  if (!soundEnabled) return null;
  const AudioEngine = window.AudioContext || window.webkitAudioContext;
  if (!AudioEngine) return null;
  if (!audioContext) audioContext = new AudioEngine();
  if (audioContext.state === "suspended") audioContext.resume().catch(() => {});
  return audioContext;
}
function tone(frequency, endFrequency, duration, type, volume, delay = 0) {
  const audio = ensureAudio(); if (!audio) return;
  const start = audio.currentTime + delay, oscillator = audio.createOscillator(), gain = audio.createGain();
  oscillator.type = type; oscillator.frequency.setValueAtTime(Math.max(20, frequency), start);
  oscillator.frequency.exponentialRampToValueAtTime(Math.max(20, endFrequency), start + duration);
  const amplifiedVolume = Math.min(.4, Math.max(.0002, volume * 4));
  gain.gain.setValueAtTime(.0001, start); gain.gain.exponentialRampToValueAtTime(amplifiedVolume, start + .008);
  gain.gain.exponentialRampToValueAtTime(.0001, start + duration);
  oscillator.connect(gain); gain.connect(audio.destination); oscillator.start(start); oscillator.stop(start + duration + .02);
}
function playEffect(kind, strength = 1) {
  if (!soundEnabled) return;
  const now = performance.now(), minimumGap = kind === "shot" ? 42 : kind === "explosion" ? 100 : 25;
  if (now - (soundCooldowns.get(kind) || 0) < minimumGap) return;
  soundCooldowns.set(kind, now); const volume = Math.max(.012, Math.min(.11, strength * .07));
  if (kind === "shot") tone(260, 125, .055, "square", volume * .42);
  else if (kind === "sniper") tone(720, 190, .11, "sawtooth", volume * .55);
  else if (kind === "cannon") { tone(105, 38, .2, "sawtooth", volume); tone(62, 32, .24, "square", volume * .35); }
  else if (kind === "magic") tone(430, 150, .13, "triangle", volume * .7);
  else if (kind === "laser") tone(980, 230, .14, "sawtooth", volume * .48);
  else if (kind === "explosion") { tone(88, 28, .28, "sawtooth", volume); tone(180, 48, .16, "square", volume * .35); }
  else if (kind === "hurt") tone(165, 68, .16, "square", volume * .8);
  else if (kind === "death") tone(260, 38, .42, "sawtooth", volume);
  else if (kind === "pickup") { tone(480, 880, .12, "sine", volume * .65); tone(720, 1180, .12, "sine", volume * .45, .07); }
  else if (kind === "shield") { tone(330, 660, .18, "sine", volume * .55); tone(500, 1000, .2, "sine", volume * .4, .05); }
  else if (kind === "chat") { tone(740, 920, .08, "sine", volume * .38); tone(920, 1120, .09, "sine", volume * .3, .07); }
  else if (kind === "ui") tone(420, 520, .045, "sine", volume * .24);
}
function effectVolume(x, y, snapshot) {
  const me = snapshot.players?.find(player => player.id === myId);
  if (!me || !Number.isFinite(x) || !Number.isFinite(y)) return .65;
  return Math.max(.14, 1 - Math.hypot(x - me.x, y - me.y) / 1250);
}
function playStateSounds(previous, next, receivedAt) {
  if (!soundSnapshotReady) { soundSnapshotReady = true; return; }
  const oldMe = previous.players?.find(player => player.id === myId), me = next.players?.find(player => player.id === myId);
  if (oldMe && me && me.hp < oldMe.hp) playEffect(me.hp <= 0 && oldMe.hp > 0 ? "death" : "hurt", 1);
  if (oldMe && me) {
    const gainedEffect = Object.entries(me.effects || {}).some(([kind, seconds]) => seconds > (oldMe.effects?.[kind] || 0) + 1);
    const gainedMinion = (me.minions?.length || 0) > (oldMe.minions?.length || 0);
    if (gainedEffect || gainedMinion || me.hp > oldMe.hp + 1 && oldMe.hp > 0) playEffect("pickup", .8);
  }
  const previousBullets = new Set((previous.bullets || []).map(bullet => bullet.id));
  for (const bullet of next.bullets || []) {
    if (previousBullets.has(bullet.id)) continue;
    const strength = bullet.owner === myId ? 1 : effectVolume(bullet.x, bullet.y, next);
    playEffect(bullet.kind === "cannon" ? "cannon" : bullet.kind === "sniper" ? "sniper" : bullet.kind === "mage" ? "magic" : "shot", strength);
  }
  for (const laser of next.lasers || []) if (laser.segment === 0 && (laser.age || 0) < .09) playEffect("laser", laser.owner === myId ? 1 : effectVolume(laser.x1, laser.y1, next));
  for (const blast of next.explosions || []) {
    const marker = `${Math.round(blast.x / 8)}:${Math.round(blast.y / 8)}:${Boolean(blast.magic)}`;
    if (!heardExplosions.has(marker)) { heardExplosions.set(marker, receivedAt + 800); playEffect("explosion", effectVolume(blast.x, blast.y, next)); }
  }
  for (const [marker, expires] of heardExplosions) if (expires < receivedAt) heardExplosions.delete(marker);
}
function updateSoundButton() {
  soundToggle.textContent = soundEnabled ? "🔊" : "🔇";
  soundToggle.title = soundEnabled ? "关闭音效" : "开启音效";
  soundToggle.setAttribute("aria-label", soundToggle.title);
}
soundToggle.addEventListener("click", () => {
  soundEnabled = !soundEnabled;
  try { localStorage.setItem("neon-sound", soundEnabled ? "on" : "off"); } catch {}
  updateSoundButton(); if (soundEnabled) { ensureAudio(); playEffect("ui"); }
});
updateSoundButton();
function updatePowerLabel() {
  const me = state.players.find(player => player.id === myId), effects = Object.entries(me?.effects || {});
  const labels = effects.map(([kind, seconds]) => { const effect = POWERUPS[kind] || { icon: "◆", name: kind }; return `${effect.icon} ${effect.name} ${seconds.toFixed(1)}s`; });
  if (me?.infected) labels.unshift("☣ 靠近尸体5秒可完成感染");
  if (me?.minions?.length) labels.push(`◉ 战斗随从 ×${me.minions.length}`);
  if (me?.role === "weaponmaster" && !effects.some(([kind]) => ["multishot", "laser", "beam", "ricochet", "cannon"].includes(kind))) labels.push(`⚒ 随机武器 ${Math.ceil(me.weapon_cooldown)}s`);
  if (me?.role === "paladin" && !me.effects?.invincible) labels.push(me.ability_cooldown > 0 ? `✧ 圣盾冷却 ${Math.ceil(me.ability_cooldown)}s` : "✧ 圣盾已就绪（空格）");
  if (me?.infected && me.hp > 0) { const skill = INFECTED_SKILLS[me.zombie_form] || "感染技能"; labels.push(me.ability_cooldown > 0 ? `☣ ${skill}冷却 ${Math.ceil(me.ability_cooldown)}s` : `☣ ${skill}已就绪（空格）`); }
  if (me?.last_survivor) labels.push("★ 孤勇者：双倍生命、伤害+60%、减伤50%");
  if (["upgrade", "bio"].includes(requestedMode)) for (const [kind, rank] of Object.entries(me?.upgrades || {})) if (rank) labels.push(`${UPGRADE_INFO[kind]?.name || kind} Lv.${rank}`);
  if (requestedMode === "bio" && state.bio?.rescue_enabled) labels.push("✚ 救援模式已开启");
  const fallback = requestedMode === "bio" ? "探索地图并消灭僵尸，留意掉落物" : requestedMode === "upgrade" ? "击败敌人获取经验，拾取血包恢复生命" : "寻找地图上的发光道具";
  const visibleLabels = labels.slice(0, 4), hiddenCount = labels.length - visibleLabels.length;
  powerLabel.textContent = labels.length ? `${visibleLabels.join("　")}${hiddenCount > 0 ? `　＋${hiddenCount}项` : ""}` : fallback;
  powerLabel.title = labels.length ? labels.join("\n") : fallback;
}
const KEY_CODES = { KeyW: "w", KeyA: "a", KeyS: "s", KeyD: "d", ArrowUp: "arrowup", ArrowDown: "arrowdown", ArrowLeft: "arrowleft", ArrowRight: "arrowright", Space: " " };
function updateKey(event, pressed) {
  if (event.target.matches?.("input, textarea, select")) return;
  const key = KEY_CODES[event.code] || event.key.toLowerCase();
  if (pressed && event.repeat) { if (["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(key)) event.preventDefault(); return; }
  keys[key] = pressed;
  if (["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(key)) {
    event.preventDefault();
    sendInput(performance.now(), true);
  }
}
addEventListener("keydown", event => {
  if ((event.code === "Escape" || event.key === "Escape") && !guidePanel.hidden) {
    event.preventDefault(); closeGuide(); return;
  }
  if ((event.code === "Escape" || event.key === "Escape") && !roomBrowser.hidden) {
    event.preventDefault(); closeRoomBrowser(); return;
  }
  updateKey(event, true);
  if (event.code === "Escape" || event.key === "Escape") { ws?.close(); location.reload(); }
});
addEventListener("keyup", event => updateKey(event, false));
// 部分手机浏览器和内嵌浏览器会在地址栏/画布焦点变化时短暂触发 blur。
// 页面仍可见时保留输入，避免角色先本地移动、随后被服务器拉回原位。
addEventListener("blur", () => { if (document.hidden) stopGameInput(); });
addEventListener("focus", () => sendInput(performance.now(), true));
document.addEventListener("visibilitychange", () => { if (document.hidden) stopGameInput(); });
canvas.addEventListener("pointermove", event => {
  if (event.pointerType !== "touch") { mouse.x = event.clientX; mouse.y = event.clientY; }
});
canvas.addEventListener("pointerdown", event => {
  if (event.pointerType === "touch") { event.preventDefault(); if (autoAimEnabled) { autoFirePointer = event.pointerId; touchAutoShoot = true; canvas.setPointerCapture?.(event.pointerId); sendInput(performance.now(), true); } return; }
  event.preventDefault(); canvas.focus({ preventScroll: true }); mouse.x = event.clientX; mouse.y = event.clientY; mouse.down = true;
  canvas.setPointerCapture?.(event.pointerId);
  sendInput(performance.now(), true);
});
function stopShooting(event) {
  if (event.pointerType === "touch") { if (event.pointerId === autoFirePointer) { autoFirePointer = null; touchAutoShoot = false; sendInput(performance.now(), true); } }
  else { mouse.down = false; sendInput(performance.now(), true); }
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
addEventListener("pointerup", event => { stopShooting(event); resetJoystick(event); resetAimJoystick(event); });
addEventListener("pointercancel", event => { stopShooting(event); resetJoystick(event); resetAimJoystick(event); });
function sendInput(now = performance.now(), force = false) {
  if (!ws || ws.readyState !== WebSocket.OPEN || ws.bufferedAmount > (force ? 1048576 : 65536) || (!force && now - lastSend < 33)) return;
  const me = state.players.find(player => player.id === myId); if (!me) return;
  if (requestedMode === "profession" && me.ready !== true) return;
  const movement = currentMoveVector(), aimOrigin = predictedSelf || me, canvasRect = canvas.getBoundingClientRect();
  const screenX = canvasRect.left + (aimOrigin.x - camera.x) * viewScale, screenY = canvasRect.top + (aimOrigin.y - camera.y) * viewScale;
  const autoTarget = autoAimEnabled ? nearestAutoAimTarget(me, aimOrigin) : null;
  const angle = autoTarget ? Math.atan2(autoTarget.y - aimOrigin.y, autoTarget.x - aimOrigin.x) : touchAim.active ? Math.atan2(touchAim.y, touchAim.x) : Math.atan2(mouse.y - screenY, mouse.x - screenX);
  const sequence = ++inputSequence;
  if (lastSentMoving && !movement.moving) lastStopSequence = sequence;
  lastSentMoving = movement.moving; lastSend = now;
  ws.send(JSON.stringify({ type: "input", seq: sequence,
    up: keys.w || keys.arrowup || touchMove.y < -.18, down: keys.s || keys.arrowdown || touchMove.y > .18,
    left: keys.a || keys.arrowleft || touchMove.x < -.18, right: keys.d || keys.arrowright || touchMove.x > .18,
    move_x: movement.x, move_y: movement.y,
    shoot: mouse.down || touchAim.active || (touchAutoShoot && Boolean(autoTarget)), ability: Boolean(keys[" "]), angle }));
}
function nearestAutoAimTarget(me, origin) {
  let targets;
  if (requestedMode === "bio") targets = me.infected ? state.players.filter(player => !player.infected && player.hp > 0) : [...(state.zombies || []), ...state.players.filter(player => player.infected && player.hp > 0)];
  else targets = state.players.filter(player => player.id !== myId && player.hp > 0 && player.ready);
  return targets.reduce((best, target) => !best || Math.hypot(target.x - origin.x, target.y - origin.y) < Math.hypot(best.x - origin.x, best.y - origin.y) ? target : best, null);
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
function reconcilePrediction(me) {
  if (!me?.ready || me.hp <= 0) { predictedSelf = null; lastStopSequence = -1; lastSentMoving = false; return; }
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
function playerMoveSpeed(player) {
  const bioAgility = requestedMode === "bio" ? Math.min(.8, .05 * (player.upgrades?.agility || 0)) : .06 * (player.upgrades?.agility || 0);
  let speed = player.infected ? INFECTED_MOVE_SPEEDS[player.zombie_form] || 300 : 300;
  speed *= (player.effects?.speed ? 1.45 : 1) * (1 + bioAgility);
  if (player.effects?.infected_frenzy) speed *= 1.45;
  if (player.last_survivor && !player.infected) speed *= 1.35;
  return speed;
}
function updateLocalPrediction(now) {
  const dt = Math.min(Math.max(0, now - lastFrame) / 1000, .15); lastFrame = now; frameDeltaSeconds = dt || 1 / 60;
  const me = state.players.find(player => player.id === myId);
  if (!me?.ready || me.hp <= 0) { predictedSelf = null; lastStopSequence = -1; lastSentMoving = false; return; }
  if (!predictedSelf) predictedSelf = { x: me.x, y: me.y };
  const movement = currentMoveVector();
  const speed = playerMoveSpeed(me), radius = 25;
  predictionBlocked = false;
  if (movement.moving) {
    // 低帧率时保留真实经过时间，并用小步碰撞防止穿墙；不再丢掉 50ms 以外的移动时间。
    const movementSteps = Math.max(1, Math.ceil(dt / .025)), movementDt = dt / movementSteps;
    for (let step = 0; step < movementSteps; step++) {
      const nextX = Math.max(radius, Math.min(world.width - radius, predictedSelf.x + movement.x * speed * movementDt));
      if (!(state.obstacles || []).some(obstacle => predictedCircleHitsRect(nextX, predictedSelf.y, radius, obstacle))) predictedSelf.x = nextX; else predictionBlocked = true;
      const nextY = Math.max(radius, Math.min(world.height - radius, predictedSelf.y + movement.y * speed * movementDt));
      if (!(state.obstacles || []).some(obstacle => predictedCircleHitsRect(predictedSelf.x, nextY, radius, obstacle))) predictedSelf.y = nextY; else predictionBlocked = true;
    }
  }
  if (!movement.moving && lastStopSequence >= 0 && (me.input_seq ?? -1) < lastStopSequence) return;
  const stateAge = Math.max(0, now - stateReceivedAt) / 1000;
  const baseLead = Math.min(.16, Math.max(.025, (latency ?? 140) / 2000));
  const lead = movement.moving ? Math.min(.2, baseLead + stateAge) : 0;
  let targetX = me.x, targetY = me.y;
  const targetNextX = Math.max(radius, Math.min(world.width - radius, targetX + movement.x * speed * lead));
  if (!(state.obstacles || []).some(obstacle => predictedCircleHitsRect(targetNextX, targetY, radius, obstacle))) targetX = targetNextX;
  const targetNextY = Math.max(radius, Math.min(world.height - radius, targetY + movement.y * speed * lead));
  if (!(state.obstacles || []).some(obstacle => predictedCircleHitsRect(targetX, targetNextY, radius, obstacle))) targetY = targetNextY;
  const errorX = targetX - predictedSelf.x, errorY = targetY - predictedSelf.y, error = Math.hypot(errorX, errorY);
  if (error > 260) { predictedSelf.x = targetX; predictedSelf.y = targetY; return; }
  if (error < .15) return;
  if (!movement.moving) {
    if (error <= .75) return;
    // 停止后只做柔和的服务器校正，禁止小误差直接瞬移造成公网玩家视觉抽动。
    const step = Math.min(error * (1 - Math.exp(-6 * dt)), 90 * dt);
    predictedSelf.x += errorX / error * step; predictedSelf.y += errorY / error * step;
    return;
  }
  if (predictionBlocked) {
    const step = Math.min(error * (1 - Math.exp(-12 * dt)), 300 * dt);
    predictedSelf.x += errorX / error * step; predictedSelf.y += errorY / error * step;
    return;
  }
  // 横向误差快速修正；前进方向保留一小段容差，避免网络状态帧让速度忽快忽慢。
  const parallel = errorX * movement.x + errorY * movement.y;
  const perpendicularX = errorX - parallel * movement.x, perpendicularY = errorY - parallel * movement.y;
  const perpendicularLength = Math.hypot(perpendicularX, perpendicularY);
  if (perpendicularLength > .15) {
    const step = Math.min(perpendicularLength * (1 - Math.exp(-10 * dt)), 180 * dt);
    predictedSelf.x += perpendicularX / perpendicularLength * step; predictedSelf.y += perpendicularY / perpendicularLength * step;
  }
  const excess = Math.max(0, Math.abs(parallel) - 32) * Math.sign(parallel);
  if (excess) {
    const step = Math.sign(excess) * Math.min(Math.abs(excess) * (1 - Math.exp(-2.5 * dt)), 55 * dt);
    predictedSelf.x += movement.x * step; predictedSelf.y += movement.y * step;
  }
}
function updateLatency(now) {
  if (!ws || ws.readyState !== WebSocket.OPEN || now - lastPing < 2000) return;
  lastPing = now; ws.send(JSON.stringify({ type: "ping", sent: now }));
}
function synchronizedSnapshotTime(serverTime, receivedAt) {
  if (!Number.isFinite(serverTime)) return receivedAt;
  const measuredOffset = receivedAt - serverTime;
  if (serverClockOffset === null) serverClockOffset = measuredOffset;
  else {
    const difference = measuredOffset - serverClockOffset;
    // 网络包偶尔晚到时不要把时间轴向后猛拉；更低延迟的样本则较快校准时钟。
    const adjustment = difference * (difference < 0 ? .2 : .015);
    serverClockOffset += Math.max(-8, Math.min(2, adjustment));
  }
  return serverTime + serverClockOffset;
}
function recordMotionSample(key, x, y, time, vx, vy, moving) {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return;
  let track = motionTracks.get(key), samples = track?.samples || [], last = samples.at(-1);
  if (last && Math.hypot(last.x - x, last.y - y) > 420) { samples = []; last = null; }
  if (last && time <= last.time) time = last.time + 1;
  const elapsed = last ? Math.max(.001, (time - last.time) / 1000) : 0;
  const sampleVx = Number.isFinite(vx) ? vx : last ? (x - last.x) / elapsed : 0;
  const sampleVy = Number.isFinite(vy) ? vy : last ? (y - last.y) / elapsed : 0;
  const sampleMoving = typeof moving === "boolean" ? moving : Math.hypot(sampleVx, sampleVy) > 8;
  const sample = { x, y, time, vx: sampleVx, vy: sampleVy, moving: sampleMoving };
  if (!samples.length && sampleMoving) {
    const delay = REMOTE_INTERPOLATION_MS / 1000;
    samples.push({ ...sample, x: x - sampleVx * delay, y: y - sampleVy * delay, time: time - REMOTE_INTERPOLATION_MS });
  }
  samples.push(sample);
  if (samples.length > 8) samples.splice(0, samples.length - 8);
  motionTracks.set(key, { samples, lastSeen: time });
}
function recordMotionSnapshots(snapshot, receivedAt) {
  const seen = new Set();
  for (const player of snapshot.players || []) {
    if (player.id !== myId) {
      const key = `p${player.id}`, speed = playerMoveSpeed(player);
      const moveX = Number(player.move_x) || 0, moveY = Number(player.move_y) || 0;
      recordMotionSample(key, player.x, player.y, receivedAt, moveX * speed, moveY * speed, Math.hypot(moveX, moveY) > .01);
      seen.add(key);
    }
    for (const minion of player.minions || []) {
      const key = `m${player.id}:${minion.id}`;
      recordMotionSample(key, minion.x, minion.y, receivedAt);
      seen.add(key);
    }
  }
  for (const bullet of snapshot.bullets || []) {
    if (bullet.id === undefined) continue;
    const key = `b${bullet.id}`;
    recordMotionSample(key, bullet.x, bullet.y, receivedAt, bullet.vx || 0, bullet.vy || 0, true);
    seen.add(key);
  }
  for (const zombie of snapshot.zombies || []) {
    const speeds = { runner: 195, giant: 58, raider: 150, infector: 92, vomiter: 68, shooter: 78, normal: 105 };
    const key = `z${zombie.id}`, speed = zombie.boss ? 150 : speeds[zombie.kind] || 105;
    recordMotionSample(key, zombie.x, zombie.y, receivedAt, (zombie.move_x || 0) * speed, (zombie.move_y || 0) * speed,
                       Math.hypot(zombie.move_x || 0, zombie.move_y || 0) > .01);
    seen.add(key);
  }
  for (const key of motionTracks.keys()) if (!seen.has(key)) motionTracks.delete(key);
}
function sampledMotionPoint(key, now, fallbackX, fallbackY, interpolationMs = REMOTE_INTERPOLATION_MS, extrapolationMs = REMOTE_EXTRAPOLATION_MS) {
  const track = motionTracks.get(key), samples = track?.samples;
  if (!samples?.length) return { x: fallbackX, y: fallbackY };
  const renderTime = now - interpolationMs;
  while (samples.length > 2 && samples[1].time <= renderTime) samples.shift();
  const first = samples[0], second = samples[1];
  if (second && renderTime <= second.time) {
    const span = Math.max(1, second.time - first.time), amount = Math.max(0, Math.min(1, (renderTime - first.time) / span));
    return { x: first.x + (second.x - first.x) * amount, y: first.y + (second.y - first.y) * amount };
  }
  const latest = samples.at(-1);
  if (!latest.moving) return { x: latest.x, y: latest.y };
  const extra = Math.max(0, Math.min(extrapolationMs, renderTime - latest.time)) / 1000;
  return { x: latest.x + latest.vx * extra, y: latest.y + latest.vy * extra };
}
function smoothedPlayers(now) {
  const players = state.players.map(player => {
    const playerKey = `p${player.id}`;
    const point = player.id === myId && predictedSelf && player.ready ? predictedSelf : sampledMotionPoint(playerKey, now, player.x, player.y);
    const minions = (player.minions || []).map(minion => {
      const key = `m${player.id}:${minion.id}`, minionPoint = sampledMotionPoint(key, now, minion.x, minion.y);
      return { ...minion, x: minionPoint.x, y: minionPoint.y };
    });
    return { ...player, x: point.x, y: point.y, minions };
  });
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
  const x = o.x - camera.x, y = o.y - camera.y;
  if (!o.active) {
    ctx.save(); ctx.globalAlpha = .32; ctx.strokeStyle = "#607da8"; ctx.lineWidth = 1; ctx.setLineDash([4, 5]);
    ctx.strokeRect(x + 2, y + 2, o.w - 4, o.h - 4); ctx.setLineDash([]);
    ctx.fillStyle = "#b8cff1"; ctx.font = "10px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(Math.ceil(o.restore), x + o.w / 2, y + o.h / 2); ctx.restore(); return;
  }
  const gradient = ctx.createLinearGradient(x, y, x, y + o.h);
  gradient.addColorStop(0, "#314665"); gradient.addColorStop(1, "#17243b"); ctx.fillStyle = gradient; ctx.strokeStyle = "#607da8"; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.roundRect(x, y, o.w, o.h, 9); ctx.fill(); ctx.stroke(); ctx.strokeStyle = "#233653"; ctx.lineWidth = 2;
  for (let offset = 20; offset < o.w; offset += 38) { ctx.beginPath(); ctx.moveTo(x + offset, y + 4); ctx.lineTo(x + offset - 14, y + o.h - 4); ctx.stroke(); }
}
function rebuildBioTerrainCache(signature) {
  bioTerrainCache.width = world.width; bioTerrainCache.height = world.height;
  const terrainContext = bioTerrainCache.getContext("2d"); terrainContext.clearRect(0, 0, world.width, world.height);
  for (const obstacle of state.obstacles || []) {
    if (!obstacle.active) continue;
    const gradient = terrainContext.createLinearGradient(obstacle.x, obstacle.y, obstacle.x, obstacle.y + obstacle.h);
    gradient.addColorStop(0, "#314665"); gradient.addColorStop(1, "#17243b");
    terrainContext.fillStyle = gradient; terrainContext.strokeStyle = "#607da8"; terrainContext.lineWidth = 3;
    terrainContext.beginPath(); terrainContext.roundRect(obstacle.x, obstacle.y, obstacle.w, obstacle.h, 9); terrainContext.fill(); terrainContext.stroke();
    terrainContext.strokeStyle = "#233653"; terrainContext.lineWidth = 2;
    for (let offset = 20; offset < obstacle.w; offset += 38) { terrainContext.beginPath(); terrainContext.moveTo(obstacle.x + offset, obstacle.y + 4); terrainContext.lineTo(obstacle.x + offset - 14, obstacle.y + obstacle.h - 4); terrainContext.stroke(); }
  }
  bioTerrainSignature = signature;
}
function drawTerrain() {
  if (requestedMode !== "bio") { (state.obstacles || []).forEach(drawObstacle); return; }
  const destroyed = (state.obstacles || []).filter(obstacle => !obstacle.active);
  const signature = destroyed.map(obstacle => obstacle.id).join(",");
  if (bioTerrainCache.width !== world.width || bioTerrainCache.height !== world.height || signature !== bioTerrainSignature) rebuildBioTerrainCache(signature);
  const sourceWidth = Math.min(sceneWidth, world.width - camera.x), sourceHeight = Math.min(sceneHeight, world.height - camera.y);
  if (sourceWidth > 0 && sourceHeight > 0) ctx.drawImage(bioTerrainCache, camera.x, camera.y, sourceWidth, sourceHeight, 0, 0, sourceWidth, sourceHeight);
  destroyed.forEach(drawObstacle);
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
function drawHazards(now) {
  for (const hazard of state.hazards || []) {
    if (!visible(hazard.x, hazard.y, 0, 0, hazard.radius)) continue;
    const pulse = .88 + Math.sin(now / 130 + hazard.id) * .08, x = hazard.x - camera.x, y = hazard.y - camera.y;
    ctx.save(); ctx.globalAlpha = Math.min(.58, .25 + hazard.life * .025); ctx.fillStyle = "#6eb52c"; ctx.strokeStyle = "#b2ff55"; ctx.lineWidth = 3; ctx.shadowBlur = mobileMode ? 7 : 18; ctx.shadowColor = "#76ff35";
    ctx.beginPath(); ctx.arc(x, y, hazard.radius * pulse, 0, Math.PI * 2); ctx.fill(); ctx.setLineDash([8, 7]); ctx.stroke(); ctx.restore();
  }
}
function zombiePoint(zombie, now) {
  return sampledMotionPoint(`z${zombie.id}`, now, zombie.x, zombie.y, 115, 70);
}
function drawZombies(now) {
  for (const zombie of state.zombies || []) {
    const point = zombiePoint(zombie, now);
    if (!visible(point.x, point.y, 0, 0, zombie.radius + 12)) continue;
    const x = point.x - camera.x, y = point.y - camera.y, radius = zombie.radius || 20;
    const colors = { normal: "#70c957", shooter: "#b875ff", giant: "#9c6b45", runner: "#d4f05a", raider: "#ff944d", infector: "#42e6b4", vomiter: "#a5cf39",
                     plague_lord: "#70ff70", brood_queen: "#ff5ab7", iron_abomination: "#ff704d" };
    const color = colors[zombie.kind] || "#77cc66";
    ctx.save(); ctx.shadowColor = color; ctx.shadowBlur = zombie.boss ? 28 : mobileMode ? 6 : 14;
    ctx.fillStyle = zombie.boss ? "#27101b" : "#172316"; ctx.strokeStyle = color; ctx.lineWidth = zombie.boss ? 5 : 3;
    ctx.beginPath();
    if (["runner", "raider"].includes(zombie.kind)) ctx.moveTo(x, y - radius), ctx.lineTo(x + radius, y + radius), ctx.lineTo(x - radius, y + radius), ctx.closePath();
    else ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke(); ctx.shadowBlur = 0;
    ctx.fillStyle = zombie.kind === "shooter" ? "#e8c7ff" : "#ff435f";
    ctx.beginPath(); ctx.arc(x - radius * .34, y - radius * .18, Math.max(2, radius * .11), 0, Math.PI * 2); ctx.arc(x + radius * .34, y - radius * .18, Math.max(2, radius * .11), 0, Math.PI * 2); ctx.fill();
    const barWidth = Math.max(34, radius * 2.2); ctx.fillStyle = "#25172a"; ctx.fillRect(x - barWidth / 2, y + radius + 9, barWidth, 5);
    ctx.fillStyle = zombie.boss ? "#ff4365" : "#81e66c"; ctx.fillRect(x - barWidth / 2, y + radius + 9, barWidth * Math.max(0, zombie.hp) / zombie.max_hp, 5);
    if (zombie.boss) { ctx.fillStyle = "#ffd6df"; ctx.font = "bold 13px sans-serif"; ctx.textAlign = "center"; ctx.fillText(zombie.boss_name, x, y - radius - 12); }
    ctx.restore();
  }
}
function revealBioCellsAt(x, y) {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return;
  const cell = 140, centerX = Math.floor(x / cell), centerY = Math.floor(y / cell);
  for (let offsetY = -2; offsetY <= 2; offsetY++) for (let offsetX = -2; offsetX <= 2; offsetX++)
    if (offsetX * offsetX + offsetY * offsetY <= 6) exploredBioCells.add(`${centerX + offsetX},${centerY + offsetY}`);
}
function updateBioExploration(me) {
  if (requestedMode !== "bio" || !me) return;
  // 小地图探索由同阵营的存活队友共同贡献，幸存者与感染阵营互不共享。
  for (const teammate of state.players || [])
    if (teammate.ready && teammate.hp > 0 && Boolean(teammate.infected) === Boolean(me.infected)) revealBioCellsAt(teammate.x, teammate.y);
}
function bioCellExplored(x, y) { return exploredBioCells.has(`${Math.floor(x / 140)},${Math.floor(y / 140)}`); }
function drawBioFog(me) {
  if (requestedMode !== "bio" || !me) return;
  const x = me.x - camera.x, y = me.y - camera.y, gradient = ctx.createRadialGradient(x, y, 170, x, y, 540);
  gradient.addColorStop(0, "#00000000"); gradient.addColorStop(.52, "#0206050a"); gradient.addColorStop(.8, "#010303b8"); gradient.addColorStop(1, "#000000fa");
  ctx.save(); ctx.fillStyle = gradient; ctx.fillRect(0, 0, sceneWidth, sceneHeight); ctx.restore();
}
function drawBioMinimap(me, now) {
  if (requestedMode !== "bio" || !me) return;
  const width = Math.min(210, viewWidth * .34), height = width * world.height / world.width;
  const x = viewWidth - width - 14, y = 62, scaleX = width / world.width, scaleY = height / world.height;
  ctx.save(); ctx.fillStyle = "#030706ee"; ctx.strokeStyle = "#4d775f"; ctx.lineWidth = 2; ctx.beginPath(); ctx.roundRect(x, y, width, height, 10); ctx.fill(); ctx.stroke(); ctx.beginPath(); ctx.roundRect(x, y, width, height, 10); ctx.clip();
  const cell = 140;
  for (const key of exploredBioCells) { const [column, row] = key.split(",").map(Number); ctx.fillStyle = "#14261d"; ctx.fillRect(x + column * cell * scaleX, y + row * cell * scaleY, cell * scaleX + 1, cell * scaleY + 1); }
  ctx.fillStyle = "#344b40";
  for (const wall of state.obstacles || []) if (wall.active && bioCellExplored(wall.x + wall.w / 2, wall.y + wall.h / 2)) ctx.fillRect(x + wall.x * scaleX, y + wall.y * scaleY, Math.max(1, wall.w * scaleX), Math.max(1, wall.h * scaleY));
  for (const player of state.players || []) if (bioCellExplored(player.x, player.y)) { ctx.fillStyle = player.infected ? "#9cff57" : player.id === myId ? "#72f1d0" : player.color; ctx.beginPath(); ctx.arc(x + player.x * scaleX, y + player.y * scaleY, player.id === myId ? 4 : 3, 0, Math.PI * 2); ctx.fill(); }
  for (const zombie of state.zombies || []) if (Math.hypot(zombie.x - me.x, zombie.y - me.y) < 430) { ctx.fillStyle = zombie.boss ? "#ff3155" : "#9ee866"; ctx.beginPath(); ctx.arc(x + zombie.x * scaleX, y + zombie.y * scaleY, zombie.boss ? 4 : 2, 0, Math.PI * 2); ctx.fill(); }
  ctx.restore(); ctx.fillStyle = "#9eb6a8"; ctx.font = "bold 11px sans-serif"; ctx.textAlign = "right"; ctx.fillText("队伍共享探索", x + width - 7, y + height - 7);
}
function drawBioWaveHud() {
  if (requestedMode !== "bio" || !state.bio) return;
  const bio = state.bio, population = `幸存 ${bio.survivor_players ?? 0} · 感染 ${bio.infected_players ?? 0}`, label = bio.active ? `第 ${bio.wave} 波 · 剩余 ${bio.remaining} · ${population}` : bio.wave ? `第 ${bio.wave} 波完成 · ${Math.ceil(bio.next_wave)} 秒后继续 · ${population}` : `感染逼近 · ${Math.ceil(bio.next_wave)} 秒 · ${population}`;
  ctx.save(); ctx.textAlign = "center"; ctx.font = "bold 17px sans-serif"; ctx.fillStyle = bio.boss ? "#ff6b86" : "#d8ffe2"; ctx.shadowColor = bio.boss ? "#ff3155" : "#57d98b"; ctx.shadowBlur = 12; ctx.fillText(bio.boss ? `${label} · BOSS ${bio.boss} · 强度 ${bio.boss_tier}` : label, viewWidth / 2, 32); ctx.restore();
}
function drawPlayer(p) {
  if (!p.ready) return;
  if (!visible(p.x, p.y)) return;
  const x = p.x - camera.x, y = p.y - camera.y, dead = p.hp <= 0; ctx.save(); ctx.globalAlpha = dead ? .22 : 1;
  if (p.effects?.shield) { ctx.fillStyle = "#55e6ff22"; ctx.strokeStyle = "#55e6ff"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, 34, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); }
  if (p.effects?.invincible || p.upgrading || p.last_survivor) { const auraColor = p.last_survivor ? "#ffcf4a" : p.upgrading ? "#72f1d0" : "#ffe17a"; ctx.fillStyle = p.last_survivor ? "#ffb21c35" : p.upgrading ? "#72f1d02a" : "#ffe17a2a"; ctx.strokeStyle = auraColor; ctx.lineWidth = p.last_survivor ? 6 : 5; ctx.shadowBlur = mobileMode ? 10 : 25; ctx.shadowColor = auraColor; ctx.beginPath(); ctx.arc(x, y, p.last_survivor ? 42 : 38, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); ctx.shadowBlur = 0; }
  const bodyColor = p.infected ? "#86e64f" : p.color;
  ctx.shadowBlur = mobileMode ? 9 : 22; ctx.shadowColor = bodyColor; ctx.fillStyle = bodyColor; ctx.beginPath(); ctx.arc(x, y, 24, 0, Math.PI * 2); ctx.fill();
  ctx.shadowBlur = 0; ctx.strokeStyle = "#fff"; ctx.lineWidth = p.id === myId ? 4 : 2; ctx.stroke();
  if (Object.keys(p.effects || {}).length) { ctx.strokeStyle = "#ffd166"; ctx.lineWidth = 2; ctx.setLineDash([4, 5]); ctx.beginPath(); ctx.arc(x, y, 31, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]); }
  ctx.globalAlpha = 1;
  if (dead && requestedMode === "bio" && state.bio?.rescue_enabled) { const progress = Math.max(0, Math.min(10, p.rescue_progress || 0)); ctx.lineWidth = 5; ctx.strokeStyle = "#263b45"; ctx.beginPath(); ctx.arc(x, y, 34, -.5 * Math.PI, 1.5 * Math.PI); ctx.stroke(); if (progress > 0) { ctx.strokeStyle = "#72f1d0"; ctx.shadowColor = "#55d6be"; ctx.shadowBlur = 12; ctx.beginPath(); ctx.arc(x, y, 34, -.5 * Math.PI, -.5 * Math.PI + Math.PI * 2 * progress / 10); ctx.stroke(); ctx.shadowBlur = 0; } }
  const deadLabel = requestedMode === "bio" ? p.infected ? (p.choosing_zombie ? "选择感染形态" : "感染体耗尽") : state.bio?.rescue_enabled ? (p.rescue_progress > 0 ? `救援中 ${p.rescue_progress.toFixed(1)}秒` : p.infection_progress > 0 ? `感染中 ${p.infection_progress.toFixed(1)}秒` : "等待救援") : "已阵亡" : "复活中…";
  ctx.fillStyle = "#eaf2ff"; ctx.font = "bold 13px sans-serif"; ctx.textAlign = "center"; ctx.fillText(dead ? deadLabel : `${p.infected ? `[感染体·${ZOMBIE_FORM_NAMES[p.zombie_form] || p.zombie_form}] ` : ["upgrade", "bio"].includes(requestedMode) ? `[Lv.${p.level || 1}] ` : ""}${p.name}`, x, y - 40);
  ctx.fillStyle = "#17213b"; ctx.fillRect(x - 26, y + 33, 52, 6); ctx.fillStyle = p.hp > p.max_hp / 2 ? "#55d6be" : "#ff5d73"; ctx.fillRect(x - 26, y + 33, 52 * Math.max(0, p.hp) / p.max_hp, 6); ctx.restore();
}
function recordSpeedTrails(players, now) {
  const active = new Set();
  for (const p of players) {
    if (!p.effects?.speed || p.hp <= 0 || !p.ready) { speedTrails.delete(p.id); speedTrailAnchors.delete(p.id); continue; }
    active.add(p.id);
    const anchor = speedTrailAnchors.get(p.id);
    if (!anchor) { speedTrailAnchors.set(p.id, { x: p.x, y: p.y, time: now }); continue; }
    const distance = Math.hypot(p.x - anchor.x, p.y - anchor.y);
    if (distance > 120) { speedTrails.delete(p.id); speedTrailAnchors.set(p.id, { x: p.x, y: p.y, time: now }); continue; }
    if (distance >= 9 && now - anchor.time >= 28) {
      const trail = speedTrails.get(p.id) || [];
      trail.push({ x: anchor.x, y: anchor.y, color: p.color, created: now });
      if (trail.length > 6) trail.shift();
      speedTrails.set(p.id, trail); speedTrailAnchors.set(p.id, { x: p.x, y: p.y, time: now });
    }
  }
  for (const id of speedTrailAnchors.keys()) if (!active.has(id)) { speedTrailAnchors.delete(id); speedTrails.delete(id); }
}
function drawSpeedTrails(now) {
  for (const [id, trail] of speedTrails) {
    for (const ghost of trail) {
      const progress = Math.max(0, Math.min(1, (now - ghost.created) / 220));
      if (!visible(ghost.x, ghost.y) || progress >= 1) continue;
      ctx.save(); ctx.globalAlpha = .46 * (1 - progress) ** 1.4; ctx.fillStyle = ghost.color; ctx.shadowBlur = mobileMode ? 5 : 14; ctx.shadowColor = ghost.color;
      ctx.beginPath(); ctx.arc(ghost.x - camera.x, ghost.y - camera.y, 22, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    }
    const remainingTrail = trail.filter(ghost => now - ghost.created < 220);
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
function sampledBulletPoint(bullet, now) {
  const samples = motionTracks.get(`b${bullet.id}`)?.samples;
  if (!samples?.length) return { x: bullet.x, y: bullet.y };
  const latest = samples.at(-1);
  const seconds = Math.max(0, Math.min(BULLET_EXTRAPOLATION_MS, now - latest.time)) / 1000;
  return extrapolatedBulletPosition({ ...bullet, x: latest.x, y: latest.y, vx: latest.vx, vy: latest.vy }, seconds);
}
function drawProjectiles(now) {
  for (const l of state.lasers || []) { let laserX1 = l.x1, laserY1 = l.y1; if (l.owner === myId && l.segment === 0 && predictedSelf && (l.age || 0) < .18) { const blend = 1 - (l.age || 0) / .18; laserX1 += (predictedSelf.x - l.x1) * blend; laserY1 += (predictedSelf.y - l.y1) * blend; } if (!visible(Math.min(laserX1, l.x2), Math.min(laserY1, l.y2), Math.abs(l.x2 - laserX1), Math.abs(l.y2 - laserY1))) continue; ctx.save(); ctx.strokeStyle = l.color; ctx.shadowColor = l.color; ctx.shadowBlur = mobileMode ? 8 : l.beam ? 17 : 25; ctx.lineWidth = l.beam ? 7 : 11; ctx.globalAlpha = l.beam ? .18 : .25; ctx.beginPath(); ctx.moveTo(laserX1 - camera.x, laserY1 - camera.y); ctx.lineTo(l.x2 - camera.x, l.y2 - camera.y); ctx.stroke(); ctx.lineWidth = l.beam ? 2.5 : 4; ctx.globalAlpha = 1; ctx.beginPath(); ctx.moveTo(laserX1 - camera.x, laserY1 - camera.y); ctx.lineTo(l.x2 - camera.x, l.y2 - camera.y); ctx.stroke(); ctx.restore(); }
  for (const b of state.bullets || []) { let bulletPoint = sampledBulletPoint(b, now); if (b.owner === myId && predictedSelf && (b.age || 0) < .18) { const serverMe = state.players.find(player => player.id === myId), blend = 1 - (b.age || 0) / .18; if (serverMe) bulletPoint = { x: bulletPoint.x + (predictedSelf.x - serverMe.x) * blend, y: bulletPoint.y + (predictedSelf.y - serverMe.y) * blend }; } const bulletX = bulletPoint.x, bulletY = bulletPoint.y; if (!visible(bulletX, bulletY)) continue; const radius = b.radius || 6; ctx.fillStyle = b.color; ctx.shadowBlur = mobileMode ? 7 : b.kind === "cannon" ? 28 : 16; ctx.shadowColor = b.color; ctx.beginPath(); ctx.arc(bulletX - camera.x, bulletY - camera.y, radius, 0, Math.PI * 2); ctx.fill(); if (b.kind === "cannon") { ctx.strokeStyle = "#ffe2a8"; ctx.lineWidth = 4; ctx.stroke(); } else if (["zombie", "vomit", "infected", "infected_vomit"].includes(b.kind)) { ctx.strokeStyle = b.kind.includes("vomit") ? "#e4ff75" : "#d8ff9c"; ctx.lineWidth = 2; ctx.stroke(); ctx.fillStyle = b.kind.includes("vomit") ? "#65851f" : "#264b1c"; ctx.beginPath(); ctx.arc(bulletX - camera.x, bulletY - camera.y, Math.max(2, radius - 4), 0, Math.PI * 2); ctx.fill(); } else if (b.kind === "mage") { ctx.strokeStyle = "#fff"; ctx.lineWidth = 3; ctx.stroke(); } else if (b.kind === "sniper") { ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(bulletX - camera.x, bulletY - camera.y, 2, 0, Math.PI * 2); ctx.fill(); } else if (b.bounces > 0) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke(); } } ctx.shadowBlur = 0;
  for (const blast of state.explosions || []) { if (!visible(blast.x, blast.y, 0, 0, blast.radius)) continue; const total = blast.magic ? .25 : .35, alpha = Math.max(0, blast.life / total), radius = blast.radius * (1 - alpha * .45); ctx.save(); ctx.globalAlpha = alpha; ctx.fillStyle = `${blast.color}44`; ctx.strokeStyle = blast.magic ? "#f6e8ff" : blast.color; ctx.lineWidth = blast.magic ? 4 : 7; ctx.shadowBlur = mobileMode ? 10 : 30; ctx.shadowColor = blast.color; ctx.beginPath(); ctx.arc(blast.x - camera.x, blast.y - camera.y, radius, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); ctx.restore(); }
}
function render(now) {
  updateLocalPrediction(now); updateLatency(now);
  const displayPlayers = smoothedPlayers(now), me = displayPlayers.find(player => player.id === myId);
  updateBioExploration(me);
  recordSpeedTrails(displayPlayers, now);
  if (me) { const cameraBlend = 1 - Math.exp(-7.7 * frameDeltaSeconds); camera.x += (me.x - sceneWidth / 2 - camera.x) * cameraBlend; camera.y += (me.y - sceneHeight / 2 - camera.y) * cameraBlend; camera.x = Math.max(0, Math.min(world.width - sceneWidth, camera.x)); camera.y = Math.max(0, Math.min(world.height - sceneHeight, camera.y)); }
  ctx.save(); ctx.scale(viewScale, viewScale);
  drawGrid(); (state.pickups || []).forEach(p => drawPickup(p, now)); drawTerrain(); drawSpeedTrails(now); drawHazards(now); drawZombies(now); drawProjectiles(now); drawMinions(displayPlayers); displayPlayers.forEach(drawPlayer); drawBioFog(me);
  ctx.restore();
  const board = [...state.players].sort((a, b) => b.score - a.score); ctx.textAlign = "right"; ctx.font = "bold 14px sans-serif";
  if (requestedMode !== "bio") board.forEach((p, i) => { ctx.fillStyle = p.id === myId ? "#72f1d0" : "#c5d1e6"; ctx.fillText(`${i + 1}. ${requestedMode === "upgrade" ? `[Lv.${p.level || 1}] ` : ""}${p.name}  ${p.score}`, viewWidth - 20, 32 + i * 22); });
  drawBioMinimap(me, now); drawBioWaveHud();
  if (myId && !receivedState) { ctx.fillStyle = "#eef6ff"; ctx.font = "bold 20px sans-serif"; ctx.textAlign = "center"; ctx.fillText("正在等待服务器状态…", viewWidth / 2, viewHeight / 2); }
  sendInput(now); requestAnimationFrame(render);
}
requestAnimationFrame(render);
// 渲染循环负责低延迟发送，独立循环负责掉帧兜底；lastSend 会自动合并重复输入。
setInterval(() => sendInput(performance.now()), INPUT_INTERVAL_MS);
