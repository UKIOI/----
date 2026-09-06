import asyncio
import heapq
import json
import math
import os
import random
import secrets
import time
from pathlib import Path

from aiohttp import WSMsgType, web

ROOT = Path(__file__).parent
WIDTH, HEIGHT = 1600, 900
BIO_WIDTH, BIO_HEIGHT = 2800, 1800
TICK_RATE = 30
NETWORK_RATE = 25
PROTOCOL_VERSION = 16
BUILD_VERSION = 72
PLAYER_SPEED = 300
BULLET_SPEED = 760
CHAT_MAX_LENGTH = 120
CHAT_COOLDOWN = 0.8
COLORS = ["#ff4d6d", "#4deeea", "#5b8cff", "#ffd43b", "#b967ff", "#ff922b",
          "#8ce99a", "#f783ff", "#f8f9fa", "#00b4d8", "#d8f24a", "#ff9f9f"]
PLAYER_RADIUS = 25
POWERUP_DURATION = 10.0
POWERUP_TYPES = ("damage", "rapid", "multishot", "laser", "shield", "speed", "beam", "health",
                 "ricochet", "cannon", "minion")
WEAPON_MASTER_WEAPONS = ("multishot", "laser", "beam", "ricochet", "cannon")
BOT_ROLES = ("tank", "mage", "sniper", "necromancer", "weaponmaster", "paladin")
UPGRADE_MAX_RANKS = {"vitality": 3, "power": 3, "haste": 3, "agility": 3, "velocity": 3, "arsenal": 2}
BIO_DROP_POOL = ("damage", "rapid", "multishot", "shield", "speed", "ricochet", "cannon", "laser", "beam", "minion")
TEST_SETTING_LIMITS = {
    "player_hp": (20, 1000), "bullet_damage": (1, 200), "laser_damage": (1, 500),
    "beam_damage": (1, 100), "cannon_damage": (1, 500), "weapon_duration": (1, 60),
    "zombie_hp_scale": (.25, 5), "zombie_damage_scale": (.25, 5),
}
ZOMBIE_STATS = {
    "normal": {"hp": 65, "speed": 105, "damage": 12, "radius": 21, "xp": 1},
    "shooter": {"hp": 55, "speed": 78, "damage": 10, "radius": 20, "xp": 2},
    "giant": {"hp": 250, "speed": 58, "damage": 28, "radius": 35, "xp": 4},
    "runner": {"hp": 38, "speed": 195, "damage": 8, "radius": 14, "xp": 1},
    "raider": {"hp": 82, "speed": 120, "damage": 18, "radius": 20, "xp": 3},
    "infector": {"hp": 115, "speed": 92, "damage": 9, "radius": 23, "xp": 4},
    "vomiter": {"hp": 145, "speed": 68, "damage": 8, "radius": 27, "xp": 4},
}
BOSS_STATS = {
    "plague_lord": {"name": "瘟疫领主", "hp": 1200, "speed": 72, "damage": 16, "radius": 48, "xp": 14},
    "brood_queen": {"name": "巢群女王", "hp": 1050, "speed": 85, "damage": 18, "radius": 44, "xp": 14},
    "iron_abomination": {"name": "钢铁畸变体", "hp": 1550, "speed": 62, "damage": 34, "radius": 55, "xp": 18},
}
INFECTED_FORM_STATS = {
    "normal": {"name": "普通感染体", "hp": 110, "speed": 285, "damage": 18, "cooldown": .48},
    "raider": {"name": "突袭感染体", "hp": 82, "speed": 390, "damage": 16, "cooldown": .38},
    "shooter": {"name": "射手感染体", "hp": 78, "speed": 270, "damage": 15, "cooldown": .55},
    "giant": {"name": "巨型感染体", "hp": 260, "speed": 185, "damage": 38, "cooldown": .8},
    "vomiter": {"name": "呕吐感染体", "hp": 145, "speed": 235, "damage": 10, "cooldown": 1.5},
}
INFECTED_ABILITY_COOLDOWNS = {
    "normal": 12, "raider": 8, "shooter": 10, "giant": 14, "vomiter": 12,
    "plague_lord": 16, "brood_queen": 16, "iron_abomination": 16,
}
NAV_CELL = 50
OBSTACLES = [
    {"x": 250, "y": 150, "w": 260, "h": 55},
    {"x": 1090, "y": 150, "w": 260, "h": 55},
    {"x": 720, "y": 110, "w": 160, "h": 150},
    {"x": 180, "y": 420, "w": 70, "h": 260},
    {"x": 1350, "y": 420, "w": 70, "h": 260},
    {"x": 610, "y": 390, "w": 380, "h": 70},
    {"x": 430, "y": 650, "w": 230, "h": 60},
    {"x": 940, "y": 650, "w": 230, "h": 60},
]
BIO_OBSTACLES = [
    {"x": 260, "y": 180, "w": 520, "h": 70}, {"x": 1040, "y": 120, "w": 80, "h": 430},
    {"x": 1420, "y": 180, "w": 600, "h": 70}, {"x": 2320, "y": 140, "w": 70, "h": 500},
    {"x": 180, "y": 520, "w": 350, "h": 70}, {"x": 690, "y": 430, "w": 70, "h": 470},
    {"x": 1190, "y": 650, "w": 500, "h": 80}, {"x": 1930, "y": 450, "w": 430, "h": 70},
    {"x": 2500, "y": 760, "w": 120, "h": 500}, {"x": 220, "y": 980, "w": 530, "h": 75},
    {"x": 920, "y": 900, "w": 80, "h": 500}, {"x": 1160, "y": 1120, "w": 500, "h": 75},
    {"x": 1840, "y": 820, "w": 80, "h": 500}, {"x": 2070, "y": 1050, "w": 380, "h": 75},
    {"x": 330, "y": 1390, "w": 520, "h": 75}, {"x": 1120, "y": 1510, "w": 620, "h": 70},
    {"x": 2020, "y": 1460, "w": 560, "h": 70}, {"x": 1370, "y": 820, "w": 100, "h": 150},
]

rooms: dict[str, "Room"] = {}


def print_room_population(event="房间状态"):
    summaries = []
    for code, room in sorted(rooms.items()):
        human_count, bot_count = len(room.humans()), len(room.bots())
        summaries.append(f"{code}: {human_count} 真人" + (f" + {bot_count} 困难人机" if bot_count else ""))
    print(f"[房间人数] {event} | " + ("；".join(summaries) if summaries else "当前没有房间"), flush=True)


def clamp(value, low, high):
    return max(low, min(high, value))


def finite_number(value, fallback=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return number if math.isfinite(number) else fallback


def circle_hits_rect(x, y, radius, rect):
    closest_x = clamp(x, rect["x"], rect["x"] + rect["w"])
    closest_y = clamp(y, rect["y"], rect["y"] + rect["h"])
    return (x - closest_x) ** 2 + (y - closest_y) ** 2 < radius ** 2


def segment_hits_circle(start_x, start_y, end_x, end_y, center_x, center_y, radius):
    dx, dy = end_x - start_x, end_y - start_y
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-9:
        return math.hypot(start_x - center_x, start_y - center_y) <= radius
    amount = clamp(((center_x - start_x) * dx + (center_y - start_y) * dy) / length_squared, 0, 1)
    nearest_x, nearest_y = start_x + dx * amount, start_y + dy * amount
    return math.hypot(nearest_x - center_x, nearest_y - center_y) <= radius


def ray_rect_hit(x, y, dx, dy, rect):
    near, far, normal = -math.inf, math.inf, (0, 0)
    axes = ((x, dx, rect["x"], rect["x"] + rect["w"], (-1, 0), (1, 0)),
            (y, dy, rect["y"], rect["y"] + rect["h"], (0, -1), (0, 1)))
    for origin, direction, low, high, low_normal, high_normal in axes:
        if abs(direction) < 1e-9:
            if not low <= origin <= high:
                return None
            continue
        if direction > 0:
            entry, leave, entry_normal = (low - origin) / direction, (high - origin) / direction, low_normal
        else:
            entry, leave, entry_normal = (high - origin) / direction, (low - origin) / direction, high_normal
        if entry > near:
            near, normal = entry, entry_normal
        far = min(far, leave)
    return (near, normal) if far >= max(near, 0) and near > 0.01 else None


def build_terrain(obstacles=OBSTACLES):
    terrain, block_id = [], 0
    for obstacle in obstacles:
        y = obstacle["y"]
        while y < obstacle["y"] + obstacle["h"]:
            x = obstacle["x"]
            height = min(40, obstacle["y"] + obstacle["h"] - y)
            while x < obstacle["x"] + obstacle["w"]:
                width = min(40, obstacle["x"] + obstacle["w"] - x)
                terrain.append({"id": block_id, "x": x, "y": y, "w": width, "h": height,
                                "active": True, "restore": 0})
                block_id += 1
                x += 40
            y += 40
    return terrain


class Room:
    def __init__(self, code, mode="classic"):
        self.code = code
        self.mode = mode
        self.width, self.height = (BIO_WIDTH, BIO_HEIGHT) if mode == "bio" else (WIDTH, HEIGHT)
        self.players = {}
        self.bullets = []
        self.lasers = []
        self.explosions = []
        self.pickups = []
        self.terrain = build_terrain(BIO_OBSTACLES if mode == "bio" else OBSTACLES)
        self.next_pickup_id = 0
        self.next_minion_id = 0
        self.next_bullet_id = 0
        self.zombies = []
        self.pending_zombies = []
        self.host_id = None
        self.rescue_enabled = False
        self.rescue_progress = {}
        self.infection_progress = {}
        self.hazards = []
        self.next_hazard_id = 0
        self.test_settings = {"player_hp": 100, "bullet_damage": 25, "laser_damage": 50,
                              "beam_damage": 8, "cannon_damage": 70, "weapon_duration": POWERUP_DURATION,
                              "zombie_hp_scale": 1, "zombie_damage_scale": 1}
        self.next_zombie_id = 0
        self.wave = 0
        self.wave_active = False
        self.next_wave = time.monotonic() + 3
        self.wave_message_until = 0
        self.next_bio_pickup = time.monotonic() + 20
        self.last = time.monotonic()
        self.last_broadcast = 0
        self.task = asyncio.create_task(self.loop())

    def random_open_position(self, margin):
        for _ in range(200):
            x, y = random.randint(margin, self.width - margin), random.randint(margin, self.height - margin)
            clear_of_walls = not any(circle_hits_rect(x, y, margin, obstacle) for obstacle in self.active_terrain())
            clear_of_players = not any(math.hypot(x - p["x"], y - p["y"]) < margin + 80
                                       for p in self.players.values() if p.get("hp", 0) > 0)
            if clear_of_walls and clear_of_players:
                return x, y
        return margin, margin

    def active_terrain(self):
        return (block for block in self.terrain if block["active"])

    def restore_terrain(self, now):
        for block in self.terrain:
            if block["active"] or now < block["restore"]:
                continue
            occupied_by_player = any(
                player["hp"] > 0 and circle_hits_rect(player["x"], player["y"], PLAYER_RADIUS, block)
                for player in self.players.values())
            occupied_by_zombie = any(
                zombie["hp"] > 0 and circle_hits_rect(zombie["x"], zombie["y"], zombie["radius"], block)
                for zombie in self.zombies)
            occupied_by_minion = any(
                minion["hp"] > 0 and circle_hits_rect(minion["x"], minion["y"], 14, block)
                for player in self.players.values() for minion in player.get("minions", []))
            occupied = occupied_by_player or occupied_by_zombie or occupied_by_minion
            if occupied:
                block["restore"] = now + 0.5
            else:
                block["active"] = True

    def sync_pickups(self):
        self.pickups = [pickup for pickup in self.pickups if pickup["active"]]
        if self.mode == "bio":
            self.pickups = self.pickups[-24:]
            return
        desired = len(self.players) * 3 if self.mode == "items" else 0 if self.mode == "pure" else len(self.players)
        if len(self.pickups) > desired:
            self.pickups = self.pickups[:desired]
        while len(self.pickups) < desired:
            x, y = self.random_open_position(45)
            kind = "health" if self.mode in {"profession", "upgrade"} else random.choice(POWERUP_TYPES)
            self.pickups.append({"id": self.next_pickup_id, "kind": kind,
                                 "x": x, "y": y, "active": True})
            self.next_pickup_id += 1

    def next_player_color(self):
        used = {player["color"] for player in self.players.values()}
        return next((color for color in COLORS if color not in used), COLORS[len(self.players) % len(COLORS)])

    def bots(self):
        return [player for player in self.players.values() if player.get("is_bot")]

    def humans(self):
        return [player for player in self.players.values() if not player.get("is_bot")]

    def bio_strength_players(self):
        return [player for player in self.humans() if not player.get("infected")]

    def sync_solo_bot(self):
        bots = self.bots()
        if self.mode == "bio":
            for bot in bots:
                self.players.pop(bot["id"], None)
            self.sync_pickups()
            return
        if len(self.humans()) != 1:
            removed_ids = {bot["id"] for bot in bots}
            for bot_id in removed_ids:
                self.players.pop(bot_id, None)
            if removed_ids:
                self.bullets = [bullet for bullet in self.bullets if bullet["owner"] not in removed_ids]
                self.lasers = [laser for laser in self.lasers if laser["owner"] not in removed_ids]
            self.sync_pickups()
            return
        if bots:
            return
        now = time.monotonic()
        bot_id = f"bot-{secrets.token_hex(4)}"
        ready = self.mode != "profession"
        bot = {"id": bot_id, "name": "困难人机", "x": 0, "y": 0,
               "hp": 0, "max_hp": 100, "score": 0, "color": self.next_player_color(),
               "ws": None, "is_bot": True, "last_shot": 0, "respawn": 0,
               "effects": {}, "minions": [], "role": None, "ready": ready,
               "next_weapon": 0, "ability_ready": 0, "master_weapon": None, "last_chat": 0,
               "level": 1, "xp": 0, "upgrades": {}, "upgrade_choices": [],
               "last_input": now, "input_seq": -1, "bot_next_think": 0,
               "bot_strafe": random.choice((-1, 1)),
               "input": {"up": False, "down": False, "left": False, "right": False,
                         "move_x": 0, "move_y": 0, "shoot": False, "ability": False, "angle": 0}}
        self.players[bot_id] = bot
        if ready:
            self.spawn(bot)
        else:
            self.select_role(bot, random.choice(BOT_ROLES), now)
        self.sync_pickups()

    def path_clear(self, start_x, start_y, end_x, end_y, radius=PLAYER_RADIUS + 2):
        distance = math.hypot(end_x - start_x, end_y - start_y)
        if distance < .001:
            return True
        direction_x, direction_y = (end_x - start_x) / distance, (end_y - start_y) / distance
        for obstacle in self.active_terrain():
            expanded = {"x": obstacle["x"] - radius, "y": obstacle["y"] - radius,
                        "w": obstacle["w"] + radius * 2, "h": obstacle["h"] + radius * 2}
            hit = ray_rect_hit(start_x, start_y, direction_x, direction_y, expanded)
            if hit and hit[0] <= distance:
                return False
        return True

    def bot_steering(self, bot, goal_x, goal_y):
        dx, dy = goal_x - bot["x"], goal_y - bot["y"]
        distance = math.hypot(dx, dy)
        navigation_radius = bot.get("radius", PLAYER_RADIUS) + 3
        if distance < 4:
            return 0, 0
        if self.path_clear(bot["x"], bot["y"], goal_x, goal_y, navigation_radius):
            return dx / distance, dy / distance

        columns, rows = math.ceil(self.width / NAV_CELL), math.ceil(self.height / NAV_CELL)
        terrain = list(self.active_terrain())
        open_cache = {}

        def cell_center(cell):
            column, row = cell
            return (clamp(column * NAV_CELL + NAV_CELL / 2, navigation_radius, self.width - navigation_radius),
                    clamp(row * NAV_CELL + NAV_CELL / 2, navigation_radius, self.height - navigation_radius))

        def walkable(cell):
            if cell in open_cache:
                return open_cache[cell]
            column, row = cell
            if not (0 <= column < columns and 0 <= row < rows):
                return False
            x, y = cell_center(cell)
            result = not any(circle_hits_rect(x, y, navigation_radius, obstacle) for obstacle in terrain)
            open_cache[cell] = result
            return result

        def nearest_open(x, y):
            origin = (int(clamp(x // NAV_CELL, 0, columns - 1)), int(clamp(y // NAV_CELL, 0, rows - 1)))
            if walkable(origin):
                return origin
            for radius in range(1, 6):
                candidates = []
                for offset_x in range(-radius, radius + 1):
                    candidates.extend(((origin[0] + offset_x, origin[1] - radius),
                                       (origin[0] + offset_x, origin[1] + radius)))
                for offset_y in range(-radius + 1, radius):
                    candidates.extend(((origin[0] - radius, origin[1] + offset_y),
                                       (origin[0] + radius, origin[1] + offset_y)))
                valid = [cell for cell in candidates if walkable(cell)]
                if valid:
                    return min(valid, key=lambda cell: math.hypot(cell_center(cell)[0] - x,
                                                                  cell_center(cell)[1] - y))
            return None

        start = nearest_open(bot["x"], bot["y"])
        goal = nearest_open(goal_x, goal_y)
        if start is None or goal is None:
            return dx / distance, dy / distance
        frontier = [(0, start)]
        came_from, cost = {start: None}, {start: 0.0}
        while frontier:
            _, current = heapq.heappop(frontier)
            if current == goal:
                break
            for offset_x, offset_y in ((1, 0), (-1, 0), (0, 1), (0, -1),
                                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
                neighbour = (current[0] + offset_x, current[1] + offset_y)
                if not walkable(neighbour):
                    continue
                if offset_x and offset_y and (not walkable((current[0] + offset_x, current[1])) or
                                              not walkable((current[0], current[1] + offset_y))):
                    continue
                new_cost = cost[current] + (1.414 if offset_x and offset_y else 1)
                if new_cost >= cost.get(neighbour, math.inf):
                    continue
                cost[neighbour], came_from[neighbour] = new_cost, current
                priority = new_cost + math.hypot(goal[0] - neighbour[0], goal[1] - neighbour[1])
                heapq.heappush(frontier, (priority, neighbour))
        if goal not in came_from:
            return dx / distance, dy / distance
        path, current = [], goal
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse()
        waypoint_x, waypoint_y = cell_center(path[min(1, len(path) - 1)])
        for cell in path[2:7]:
            candidate_x, candidate_y = cell_center(cell)
            if not self.path_clear(bot["x"], bot["y"], candidate_x, candidate_y, navigation_radius):
                break
            waypoint_x, waypoint_y = candidate_x, candidate_y
        move_x, move_y = waypoint_x - bot["x"], waypoint_y - bot["y"]
        move_length = math.hypot(move_x, move_y) or 1
        return move_x / move_length, move_y / move_length

    def safest_position(self, bot, enemies):
        best = (bot["x"], bot["y"])
        best_score = -math.inf
        for distance in (240, 400, 580):
            for index in range(16):
                angle = index * math.tau / 16
                x = clamp(bot["x"] + math.cos(angle) * distance, PLAYER_RADIUS, self.width - PLAYER_RADIUS)
                y = clamp(bot["y"] + math.sin(angle) * distance, PLAYER_RADIUS, self.height - PLAYER_RADIUS)
                if any(circle_hits_rect(x, y, PLAYER_RADIUS + 3, obstacle) for obstacle in self.active_terrain()):
                    continue
                enemy_distance = min(math.hypot(enemy["x"] - x, enemy["y"] - y) for enemy in enemies)
                has_cover = not any(self.path_clear(x, y, enemy["x"], enemy["y"], 5) for enemy in enemies)
                travel = math.hypot(x - bot["x"], y - bot["y"])
                score = enemy_distance + (170 if has_cover else 0) - travel * .12
                if score > best_score:
                    best, best_score = (x, y), score
        return best

    def bot_dodge(self, bot):
        dodge_x = dodge_y = 0
        for bullet in self.bullets:
            if bullet["owner"] == bot["id"]:
                continue
            speed = math.hypot(bullet["vx"], bullet["vy"])
            if speed < 1:
                continue
            velocity_x, velocity_y = bullet["vx"] / speed, bullet["vy"] / speed
            relative_x, relative_y = bot["x"] - bullet["x"], bot["y"] - bullet["y"]
            along = relative_x * velocity_x + relative_y * velocity_y
            if not 0 < along < speed * .55:
                continue
            miss_x = relative_x - velocity_x * along
            miss_y = relative_y - velocity_y * along
            if math.hypot(miss_x, miss_y) >= PLAYER_RADIUS + bullet.get("radius", 6) + 28:
                continue
            side = 1 if velocity_x * relative_y - velocity_y * relative_x >= 0 else -1
            dodge_x += -velocity_y * side
            dodge_y += velocity_x * side
        length = math.hypot(dodge_x, dodge_y)
        return (dodge_x / length, dodge_y / length) if length else None

    def update_bots(self, now):
        for bot in self.bots():
            if self.mode == "profession" and not bot["ready"]:
                if now >= bot.get("respawn", 0):
                    self.select_role(bot, random.choice(BOT_ROLES), now)
                continue
            if not bot["ready"] or bot["hp"] <= 0 or now < bot.get("bot_next_think", 0):
                continue
            bot["bot_next_think"] = now + random.uniform(.065, .095)
            enemies = [player for player in self.humans() if player["ready"] and player["hp"] > 0]
            if not enemies:
                bot["input"].update(move_x=0, move_y=0, shoot=False, ability=False)
                continue
            target = min(enemies, key=lambda player: math.hypot(player["x"] - bot["x"], player["y"] - bot["y"]) +
                         player["hp"] * 1.15 - player.get("score", 0) * 8)
            dx, dy = target["x"] - bot["x"], target["y"] - bot["y"]
            distance = max(1, math.hypot(dx, dy))
            dodge = self.bot_dodge(bot)
            low_health = bot["hp"] <= bot.get("max_hp", 100) * .42
            health_pickups = [pickup for pickup in self.pickups if pickup["active"] and pickup["kind"] == "health"]
            useful_pickups = [pickup for pickup in self.pickups if pickup["active"] and
                              math.hypot(pickup["x"] - bot["x"], pickup["y"] - bot["y"]) <= 900]
            effects = bot.get("effects", {})
            role = bot.get("role")
            preferred = 470 if role == "sniper" else 380 if effects.get("cannon", 0) > now else 340 if role == "mage" else 300
            if dodge:
                move_x, move_y = dodge
                bot["bot_goal_kind"] = "dodge"
            elif low_health and health_pickups:
                pickup = min(health_pickups, key=lambda item: math.hypot(item["x"] - bot["x"], item["y"] - bot["y"]))
                move_x, move_y = self.bot_steering(bot, pickup["x"], pickup["y"])
                bot["bot_goal_kind"] = "health"
            elif low_health:
                safe_x, safe_y = self.safest_position(bot, enemies)
                move_x, move_y = self.bot_steering(bot, safe_x, safe_y)
                bot["bot_goal_kind"] = "cover"
            elif useful_pickups and distance > preferred - 30:
                values = {"health": 5 if bot["hp"] < bot.get("max_hp", 100) else 0,
                          "shield": 4.5, "speed": 3.7, "minion": 3.6, "cannon": 3.5, "laser": 3.5,
                          "beam": 3.2, "rapid": 3, "damage": 3, "multishot": 2.9, "ricochet": 2.7}
                pickup = max(useful_pickups, key=lambda item: values.get(item["kind"], 2.5) * 180 -
                             math.hypot(item["x"] - bot["x"], item["y"] - bot["y"]))
                move_x, move_y = self.bot_steering(bot, pickup["x"], pickup["y"])
                bot["bot_goal_kind"] = "pickup"
            elif distance > preferred + 65 or not self.path_clear(bot["x"], bot["y"], target["x"], target["y"], 5):
                move_x, move_y = self.bot_steering(bot, target["x"], target["y"])
                bot["bot_goal_kind"] = "chase"
            elif distance < preferred - 85:
                move_x, move_y = self.bot_steering(bot, bot["x"] - dx, bot["y"] - dy)
                bot["bot_goal_kind"] = "space"
            else:
                move_x, move_y = self.bot_steering(bot, bot["x"] - dy * bot["bot_strafe"], bot["y"] + dx * bot["bot_strafe"])
                bot["bot_goal_kind"] = "strafe"
                if random.random() < .12:
                    bot["bot_strafe"] *= -1
            target_move_x = target["input"].get("move_x", 0)
            target_move_y = target["input"].get("move_y", 0)
            projectile_speed = 430 if effects.get("cannon", 0) > now else 1200 if role == "sniper" else 700 if role == "mage" else BULLET_SPEED
            instant_weapon = effects.get("laser", 0) > now or effects.get("beam", 0) > now
            lead = 0 if instant_weapon else min(.75, distance / projectile_speed)
            target_speed = PLAYER_SPEED * (1.45 if target.get("effects", {}).get("speed", 0) > now else 1) * (1 + .06 * target.get("upgrades", {}).get("agility", 0))
            aim_x = target["x"] + target_move_x * target_speed * lead
            aim_y = target["y"] + target_move_y * target_speed * lead
            aim = math.atan2(aim_y - bot["y"], aim_x - bot["x"]) + random.uniform(-.018, .018)
            clear_shot = self.path_clear(bot["x"], bot["y"], target["x"], target["y"], 5)
            bot["last_input"] = now
            bot["input"].update(move_x=move_x, move_y=move_y, angle=aim,
                                shoot=distance < (1500 if instant_weapon else 1050 if role == "sniper" else 900) and clear_shot,
                                ability=role == "paladin" and distance < 620 and bot["hp"] < bot.get("max_hp", 100) * .7)

    def zombie_spawn_position(self, radius):
        players = [player for player in self.humans() if player.get("hp", 0) > 0]
        terrain = list(self.active_terrain())
        for _ in range(180):
            side = random.randrange(4)
            if side == 0:
                x, y = random.randint(radius, self.width - radius), random.randint(radius, 150)
            elif side == 1:
                x, y = random.randint(radius, self.width - radius), random.randint(self.height - 150, self.height - radius)
            elif side == 2:
                x, y = random.randint(radius, 150), random.randint(radius, self.height - radius)
            else:
                x, y = random.randint(self.width - 150, self.width - radius), random.randint(radius, self.height - radius)
            if any(circle_hits_rect(x, y, radius + 3, wall) for wall in terrain):
                continue
            if players and min(math.hypot(player["x"] - x, player["y"] - y) for player in players) < 520:
                continue
            return x, y
        return self.random_open_position(radius + 5)

    def nearby_zombie_spawn_position(self, center_x, center_y, radius, slot=0):
        terrain = list(self.active_terrain())
        for attempt in range(28):
            angle = slot * 2.399963 + attempt * .73
            distance = 105 + (attempt % 4) * 34
            x = clamp(center_x + math.cos(angle) * distance, radius, self.width - radius)
            y = clamp(center_y + math.sin(angle) * distance, radius, self.height - radius)
            if not any(circle_hits_rect(x, y, radius + 4, wall) for wall in terrain):
                return x, y
        return self.random_open_position(radius + 5)

    def spawn_zombie(self, kind, now, boss_kind=None, position=None):
        humans = max(1, len(self.bio_strength_players()))
        stats = BOSS_STATS[boss_kind] if boss_kind else ZOMBIE_STATS[kind]
        health_scale = (1 + max(0, self.wave - 1) * .1) * (1 + max(0, humans - 1) * .2) * self.test_settings["zombie_hp_scale"]
        damage_scale = (1 + max(0, self.wave - 1) * .045) * (1 + max(0, humans - 1) * .08) * self.test_settings["zombie_damage_scale"]
        radius = stats["radius"]
        x, y = position if position is not None else self.zombie_spawn_position(radius)
        zombie = {"id": self.next_zombie_id, "kind": boss_kind or kind, "boss": bool(boss_kind),
                  "boss_name": stats.get("name"), "x": x, "y": y, "radius": radius,
                  "hp": round(stats["hp"] * health_scale), "max_hp": round(stats["hp"] * health_scale),
                  "speed": stats["speed"], "damage": stats["damage"] * damage_scale, "xp": stats["xp"],
                  "last_attack": 0, "last_shot": 0, "next_think": now + random.uniform(0, .45), "next_special": now + 3,
                  "move_x": 0, "move_y": 0, "charge_until": 0, "steer_bias": random.choice((-1, 1)),
                  "disguised": kind == "raider" and self.wave > 10, "revealed": not (kind == "raider" and self.wave > 10),
                  "infection_target": None, "next_charge": 0}
        self.next_zombie_id += 1
        self.zombies.append(zombie)
        return zombie

    def start_bio_wave(self, now):
        self.wave += 1
        humans = max(1, len(self.bio_strength_players()))
        count = min(48, math.ceil((4 + self.wave * 1.55) * (.72 + humans * .48)))
        choices = ["normal"] * 7
        if self.wave >= 2:
            choices += ["runner"] * 3
        if self.wave >= 3:
            choices += ["shooter"] * 3
        if self.wave >= 4:
            choices += ["giant"] * 2
            choices += ["raider"] * 2
        if self.wave >= 5:
            choices += ["vomiter"] * 2
        if self.wave >= 6:
            choices += ["infector"]
        spawn_plan = [(random.choice(choices), None) for _ in range(count)]
        if self.wave % 5 == 0:
            spawn_plan.append(("boss", random.choice(tuple(BOSS_STATS))))
        for player in self.humans():
            if not player.get("infected"):
                continue
            self.rescale_infected_player_health(player)
            player["zombie_respawns"] = 3
            if player["hp"] <= 0:
                player["choosing_zombie"] = True
        # 每帧最多生成少量僵尸，避免波次刷新在单帧内计算全部出生点并阻塞移动同步。
        self.pending_zombies = [(now + index * .055, kind, boss_kind)
                                for index, (kind, boss_kind) in enumerate(spawn_plan)]
        self.wave_active = True
        self.wave_message_until = now + 3

    def drop_bio_pickup(self, x, y, kind):
        self.pickups.append({"id": self.next_pickup_id, "kind": kind,
                             "x": clamp(x + random.uniform(-25, 25), 30, self.width - 30),
                             "y": clamp(y + random.uniform(-25, 25), 30, self.height - 30), "active": True})
        self.next_pickup_id += 1

    def damage_zombie(self, zombie, amount, owner_id, now):
        if zombie["hp"] <= 0:
            return
        zombie["hp"] -= amount
        if zombie["hp"] > 0:
            return
        zombie["hp"] = 0
        owner = self.players.get(owner_id)
        if owner:
            owner["score"] += 1
            owner["xp"] = owner.get("xp", 0) + zombie["xp"]
            self.check_level_up(owner)
        if zombie.get("boss"):
            self.drop_bio_pickup(zombie["x"], zombie["y"], "health")
            for _ in range(2):
                self.drop_bio_pickup(zombie["x"], zombie["y"], random.choice(BIO_DROP_POOL))
        else:
            if random.random() < .07:
                self.drop_bio_pickup(zombie["x"], zombie["y"], "health")
            if random.random() < .035:
                self.drop_bio_pickup(zombie["x"], zombie["y"], random.choice(BIO_DROP_POOL))

    def zombie_steering(self, zombie, goal_x, goal_y, terrain):
        dx, dy = goal_x - zombie["x"], goal_y - zombie["y"]
        distance = math.hypot(dx, dy)
        if distance < 2:
            return 0, 0
        base_angle = math.atan2(dy, dx)
        probe = max(64, min(120, zombie["radius"] * 2.4 + zombie["speed"] * .22))

        def direction_open(angle):
            move_x, move_y = math.cos(angle), math.sin(angle)
            for scale in (.55, 1):
                x, y = zombie["x"] + move_x * probe * scale, zombie["y"] + move_y * probe * scale
                if not (zombie["radius"] <= x <= self.width - zombie["radius"] and
                        zombie["radius"] <= y <= self.height - zombie["radius"]):
                    return None
                nearby = self.nearby_terrain(terrain, x, y, zombie["radius"] + 3)
                if any(circle_hits_rect(x, y, zombie["radius"] + 3, wall) for wall in nearby):
                    return None
            return move_x, move_y

        direct = direction_open(base_angle)
        if direct:
            return direct
        # 僵尸只检查附近的绕行方向，不再各自搜索整张地图；固定偏向可避免墙边左右抖动。
        bias = zombie.get("steer_bias", 1)
        for offset in (.38, .72, 1.08, 1.46, 1.9, 2.35, math.pi):
            for side in (bias, -bias):
                candidate = direction_open(base_angle + offset * side)
                if candidate:
                    return candidate
        return 0, 0

    @staticmethod
    def terrain_collision_index(terrain):
        grid, cell = {}, 128
        for wall in terrain:
            for column in range(int(wall["x"] // cell), int((wall["x"] + wall["w"]) // cell) + 1):
                for row in range(int(wall["y"] // cell), int((wall["y"] + wall["h"]) // cell) + 1):
                    grid.setdefault((column, row), []).append(wall)
        return grid

    @staticmethod
    def nearby_terrain(terrain, x, y, radius):
        if not isinstance(terrain, dict):
            return terrain
        cell, found, seen = 128, [], set()
        for column in range(int((x - radius) // cell), int((x + radius) // cell) + 1):
            for row in range(int((y - radius) // cell), int((y + radius) // cell) + 1):
                for wall in terrain.get((column, row), ()):
                    marker = wall["id"]
                    if marker not in seen:
                        seen.add(marker)
                        found.append(wall)
        return found

    def move_zombie(self, zombie, dx, dy, dt, speed, terrain=None):
        radius = zombie["radius"]
        terrain = terrain if terrain is not None else list(self.active_terrain())
        next_x = clamp(zombie["x"] + dx * speed * dt, radius, self.width - radius)
        if not any(circle_hits_rect(next_x, zombie["y"], radius, wall) for wall in self.nearby_terrain(terrain, next_x, zombie["y"], radius)):
            zombie["x"] = next_x
        next_y = clamp(zombie["y"] + dy * speed * dt, radius, self.height - radius)
        if not any(circle_hits_rect(zombie["x"], next_y, radius, wall) for wall in self.nearby_terrain(terrain, zombie["x"], next_y, radius)):
            zombie["y"] = next_y

    def zombie_volley(self, zombie, target, now, radial=False, count=1, kind="zombie", speed=460, damage_scale=1):
        base_angle = math.atan2(target["y"] - zombie["y"], target["x"] - zombie["x"])
        angles = [index * math.tau / count for index in range(count)] if radial else [base_angle]
        for angle in angles:
            self.add_bullet({"x": zombie["x"], "y": zombie["y"], "vx": math.cos(angle) * speed,
                             "vy": math.sin(angle) * speed, "owner": f"z{zombie['id']}", "color": "#9cff57",
                             "damage": zombie["damage"] * damage_scale, "damage_type": "normal", "radius": 9 if kind == "vomit" else 7,
                             "kind": kind, "bounces": 0, "life": 3.2, "created": now})

    def create_pollution(self, x, y, now, strength=1):
        self.hazards.append({"id": self.next_hazard_id, "x": x, "y": y,
                             "radius": min(155, 78 + strength * 9), "damage": 4 + strength * 1.4,
                             "expires": now + min(12, 5.5 + strength * .7)})
        self.next_hazard_id += 1
        self.hazards = self.hazards[-20:]

    def update_hazards(self, dt, now):
        self.hazards = [hazard for hazard in self.hazards if hazard["expires"] > now]
        for hazard in self.hazards:
            for player in self.humans():
                if player["hp"] > 0 and not player.get("infected") and math.hypot(player["x"] - hazard["x"], player["y"] - hazard["y"]) < hazard["radius"]:
                    self.damage(player, hazard["damage"] * dt, "", now)

    def infect_player(self, player):
        if player.get("infected"):
            return
        base_max_hp = player.pop("last_survivor_base_max_hp", None)
        if base_max_hp is not None:
            player["max_hp"] = base_max_hp
        player.update(infected=True, choosing_zombie=True, zombie_form=None, zombie_respawns=3,
                      boss_used_wave=0, hp=0, respawn=math.inf, last_survivor=False)
        player["effects"].clear()
        player["minions"] = []
        player["input"].update(up=False, down=False, left=False, right=False,
                               move_x=0, move_y=0, shoot=False, ability=False)
        self.rescue_progress.pop(player["id"], None)
        self.infection_progress.pop(player["id"], None)

    def infected_player_max_hp(self, form):
        stats = BOSS_STATS.get(form) or INFECTED_FORM_STATS.get(form)
        if not stats:
            return None
        boss_modifier = .55 if form in BOSS_STATS else 1
        wave_scale = 1 + max(0, self.wave - 1) * .1
        return round(stats["hp"] * boss_modifier * wave_scale * self.test_settings["zombie_hp_scale"])

    def rescale_infected_player_health(self, player, refill=False):
        new_max_hp = self.infected_player_max_hp(player.get("zombie_form"))
        if new_max_hp is None:
            return
        old_max_hp = max(1, player.get("max_hp", new_max_hp))
        old_hp = player.get("hp", 0)
        player["max_hp"] = new_max_hp
        if refill:
            player["hp"] = new_max_hp
        elif old_hp > 0:
            player["hp"] = max(1, min(new_max_hp, old_hp * new_max_hp / old_max_hp))

    def select_zombie_form(self, player, form):
        if self.mode != "bio" or not player.get("infected") or not player.get("choosing_zombie"):
            return False
        boss_form = form in BOSS_STATS
        if boss_form and (self.wave == 0 or self.wave % 5 or player.get("boss_used_wave") == self.wave):
            return False
        if not boss_form and form not in INFECTED_FORM_STATS:
            return False
        stats = BOSS_STATS[form] if boss_form else INFECTED_FORM_STATS[form]
        if boss_form:
            player["boss_used_wave"] = self.wave
        # 每次选择都重新套用该形态的完整基础属性；旧形态残血和临时技能不能带入新形态。
        form_max_hp = self.infected_player_max_hp(form)
        player.update(zombie_form=form, choosing_zombie=False, max_hp=form_max_hp,
                      hp=form_max_hp, last_shot=0, shot_queued=False,
                      ability_ready=time.monotonic())
        for effect in ("infected_frenzy", "invincible", "speed"):
            player["effects"].pop(effect, None)
        player["input"].update(up=False, down=False, left=False, right=False,
                               move_x=0, move_y=0, shoot=False, ability=False)
        return True

    def update_last_survivor(self, now):
        if self.mode != "bio":
            return
        members = self.humans()
        survivors = [player for player in members
                     if player.get("ready") and player.get("hp", 0) > 0 and not player.get("infected")]
        survivor_id = survivors[0]["id"] if len(members) >= 2 and len(survivors) == 1 else None
        for player in members:
            was_active = player.get("last_survivor", False)
            active = player["id"] == survivor_id
            player["last_survivor"] = active
            if active and not was_active:
                base_max_hp = player["max_hp"]
                player["last_survivor_base_max_hp"] = base_max_hp
                player["max_hp"] = base_max_hp * 2
                player["hp"] = min(player["max_hp"], player["hp"] * 2)
                player["effects"]["invincible"] = max(player["effects"].get("invincible", 0), now + 2)
            elif was_active and not active:
                boosted_max_hp = max(1, player["max_hp"])
                base_max_hp = player.pop("last_survivor_base_max_hp", boosted_max_hp / 2)
                player["max_hp"] = base_max_hp
                player["hp"] = min(base_max_hp, player["hp"] * base_max_hp / boosted_max_hp)

    def apply_test_settings(self, values):
        for key, (minimum, maximum) in TEST_SETTING_LIMITS.items():
            if key in values:
                self.test_settings[key] = clamp(finite_number(values[key], self.test_settings[key]), minimum, maximum)
        base_hp = self.test_settings["player_hp"]
        for player in self.humans():
            if player.get("infected"):
                self.rescale_infected_player_health(player)
                continue
            old_max = max(1, player.get("max_hp", base_hp))
            vitality = player.get("upgrades", {}).get("vitality", 0)
            unboosted_max = base_hp * (3 if player.get("role") == "tank" else 1) + vitality * 15
            if player.get("last_survivor"):
                player["last_survivor_base_max_hp"] = unboosted_max
            new_max = unboosted_max * (2 if player.get("last_survivor") else 1)
            player["max_hp"] = new_max
            player["hp"] = min(new_max, player["hp"] * new_max / old_max)

    def update_zombies(self, dt, now):
        if self.mode != "bio":
            return
        self.zombies = [zombie for zombie in self.zombies if zombie["hp"] > 0]
        spawned = 0
        while self.pending_zombies and self.pending_zombies[0][0] <= now and spawned < 2:
            _, kind, boss_kind = self.pending_zombies.pop(0)
            self.spawn_zombie(kind, now, boss_kind)
            spawned += 1
        if self.wave_active and not self.zombies and not self.pending_zombies:
            self.wave_active = False
            self.next_wave = now + 5
            for player in self.humans():
                if player["hp"] > 0 and not player.get("infected"):
                    player["hp"] = min(player["max_hp"], player["hp"] + player["max_hp"] * .2)
        if not self.wave_active and now >= self.next_wave and self.humans():
            self.start_bio_wave(now)
        if now >= self.next_bio_pickup:
            self.next_bio_pickup = now + random.uniform(22, 36)
            if random.random() < .35:
                x, y = self.random_open_position(45)
                self.drop_bio_pickup(x, y, random.choice(BIO_DROP_POOL))
        targets = [player for player in self.humans() if player["ready"] and player["hp"] > 0 and not player.get("infected")]
        corpses = [player for player in self.humans() if player["ready"] and player["hp"] <= 0 and not player.get("infected")]
        active_infections = set()
        infected_players = [player for player in self.humans()
                            if player["ready"] and player["hp"] > 0 and player.get("infected") and not player.get("choosing_zombie")]
        for infected_player in infected_players:
            available_corpses = [corpse for corpse in corpses if corpse["id"] not in active_infections]
            if not available_corpses:
                break
            target = min(available_corpses, key=lambda corpse: math.hypot(
                corpse["x"] - infected_player["x"], corpse["y"] - infected_player["y"]))
            if math.hypot(target["x"] - infected_player["x"], target["y"] - infected_player["y"]) > PLAYER_RADIUS * 2 + 12:
                continue
            active_infections.add(target["id"])
            progress = self.infection_progress.get(target["id"], 0) + dt
            self.infection_progress[target["id"]] = progress
            if progress >= 5:
                self.infect_player(target)
                corpses = [corpse for corpse in corpses if corpse["id"] != target["id"]]
        if not targets and not corpses:
            return
        terrain = self.terrain_collision_index(list(self.active_terrain()))
        for zombie in self.zombies:
            infecting = zombie["kind"] == "infector" and bool(corpses)
            available_corpses = [corpse for corpse in corpses if corpse["id"] not in active_infections]
            if infecting and available_corpses:
                target = min(available_corpses, key=lambda player: math.hypot(player["x"] - zombie["x"], player["y"] - zombie["y"]))
            elif targets:
                target = min(targets, key=lambda player: math.hypot(player["x"] - zombie["x"], player["y"] - zombie["y"]))
                infecting = False
            else:
                continue
            dx, dy = target["x"] - zombie["x"], target["y"] - zombie["y"]
            distance = max(1, math.hypot(dx, dy))
            if zombie["kind"] == "raider" and distance < 360 and now >= zombie.get("next_charge", 0):
                zombie["revealed"] = True
                zombie["charge_until"] = now + 1.15
                zombie["next_charge"] = now + 4.8
            if now >= zombie["next_think"]:
                # 将大量僵尸的寻路分散到不同服务器帧，避免波次开始时集中计算导致玩家卡顿。
                zombie["next_think"] = now + random.uniform(.38, .58)
                if zombie["kind"] in {"shooter", "vomiter"} and distance < 290:
                    move_x, move_y = self.zombie_steering(zombie, zombie["x"] - dx, zombie["y"] - dy, terrain)
                elif zombie["kind"] == "shooter" and distance < 470:
                    orbit_x, orbit_y = zombie["x"] - dy / distance * 180, zombie["y"] + dx / distance * 180
                    move_x, move_y = self.zombie_steering(zombie, orbit_x, orbit_y, terrain)
                else:
                    move_x, move_y = self.zombie_steering(zombie, target["x"], target["y"], terrain)
                zombie["move_x"], zombie["move_y"] = move_x, move_y
            speed = zombie["speed"]
            if zombie["kind"] == "iron_abomination" and now < zombie["charge_until"]:
                speed *= 2.8
            if zombie["kind"] == "raider" and now < zombie["charge_until"]:
                speed *= 3.25
            self.move_zombie(zombie, zombie["move_x"], zombie["move_y"], dt, speed, terrain)
            if infecting:
                if distance <= zombie["radius"] + PLAYER_RADIUS + 10:
                    active_infections.add(target["id"])
                    progress = self.infection_progress.get(target["id"], 0) + dt
                    self.infection_progress[target["id"]] = progress
                    if progress >= 5:
                        self.infect_player(target)
                        corpses = [corpse for corpse in corpses if corpse["id"] != target["id"]]
                continue
            if distance <= zombie["radius"] + PLAYER_RADIUS + 7 and now - zombie["last_attack"] >= .8:
                zombie["last_attack"] = now
                self.damage(target, zombie["damage"], "", now)
            if zombie["kind"] == "shooter" and distance < 720 and now - zombie["last_shot"] >= 1.35 and self.path_clear(zombie["x"], zombie["y"], target["x"], target["y"], 5):
                zombie["last_shot"] = now
                self.zombie_volley(zombie, target, now)
            if zombie["kind"] == "vomiter" and distance < 780 and now >= zombie["next_special"] and self.path_clear(zombie["x"], zombie["y"], target["x"], target["y"], 7):
                zombie["next_special"] = now + 5.2
                self.zombie_volley(zombie, target, now, kind="vomit", speed=380, damage_scale=.6)
            if zombie.get("boss") and now >= zombie["next_special"]:
                tier = max(1, self.wave // 5)
                haste = 1 + (tier - 1) * .1
                if zombie["kind"] == "plague_lord":
                    zombie["next_special"] = now + 3.8 / haste
                    self.zombie_volley(zombie, target, now, radial=True, count=min(28, 12 + tier * 2), speed=480 + tier * 18)
                    self.create_pollution(target["x"], target["y"], now, tier + 1)
                    for player in targets:
                        if math.hypot(player["x"] - zombie["x"], player["y"] - zombie["y"]) < 190 + tier * 12:
                            self.damage(player, 8 + self.wave * .8, "", now)
                elif zombie["kind"] == "brood_queen":
                    zombie["next_special"] = now + 6 / haste
                    for index in range(min(8, 3 + tier)):
                        summon_kind = "raider" if tier >= 3 and index == 0 else "runner"
                        self.pending_zombies.append((now + index * .06, summon_kind, None))
                    self.pending_zombies.sort(key=lambda item: item[0])
                    self.zombie_volley(zombie, target, now, radial=True, count=min(18, 6 + tier * 2), speed=410)
                else:
                    zombie["next_special"] = now + 6.5 / haste
                    zombie["charge_until"] = now + min(3, 1.6 + tier * .18)
                    self.zombie_volley(zombie, target, now, radial=True, count=min(24, 8 + tier * 2), speed=520 + tier * 20, damage_scale=1.15)
        valid_infections = {player["id"] for player in corpses}
        self.infection_progress = {player_id: progress for player_id, progress in self.infection_progress.items()
                                   if player_id in valid_infections and player_id in active_infections}

    def add_bullet(self, bullet):
        bullet["id"] = self.next_bullet_id
        self.next_bullet_id += 1
        self.bullets.append(bullet)

    def spawn(self, player):
        x, y = self.random_open_position(PLAYER_RADIUS + 15)
        player.update(x=x, y=y, hp=player.get("max_hp", 100), respawn=0, shot_queued=False)

    @staticmethod
    def next_level_score(level):
        return level * (level + 1) // 2

    def next_level_xp(self, level):
        return math.ceil(4 * level ** 1.65) if self.mode == "bio" else self.next_level_score(level)

    def apply_upgrade(self, player, upgrade):
        if self.mode not in {"upgrade", "bio"} or upgrade not in UPGRADE_MAX_RANKS:
            return False
        ranks = player.setdefault("upgrades", {})
        if (self.mode != "bio" or upgrade == "arsenal") and ranks.get(upgrade, 0) >= UPGRADE_MAX_RANKS[upgrade]:
            return False
        ranks[upgrade] = ranks.get(upgrade, 0) + 1
        if upgrade == "vitality":
            gain = 15
            if player.get("last_survivor"):
                player["last_survivor_base_max_hp"] = player.get("last_survivor_base_max_hp", player["max_hp"] / 2) + gain
                player["max_hp"] += gain * 2
                player["hp"] = min(player["max_hp"], player["hp"] + gain * 2)
            else:
                player["max_hp"] += gain
                player["hp"] = min(player["max_hp"], player["hp"] + gain)
        player["upgrade_choices"] = []
        player.setdefault("effects", {})["invincible"] = max(
            player.get("effects", {}).get("invincible", 0), time.monotonic() + 5)
        self.check_level_up(player)
        return True

    def check_level_up(self, player):
        if self.mode not in {"upgrade", "bio"} or player.get("upgrade_choices"):
            return
        while self.mode == "bio" or player.get("level", 1) < 1 + sum(UPGRADE_MAX_RANKS.values()):
            if player.get("xp", player["score"]) < self.next_level_xp(player["level"]):
                return
            player["level"] += 1
            choices = [kind for kind, maximum in UPGRADE_MAX_RANKS.items()
                       if self.mode == "bio" and kind != "arsenal" or player.get("upgrades", {}).get(kind, 0) < maximum]
            if not choices:
                return
            player["upgrade_choices"] = random.sample(choices, min(3, len(choices)))
            if not player.get("is_bot"):
                return
            self.apply_upgrade(player, random.choice(player["upgrade_choices"]))

    def select_role(self, player, role, now=None):
        if self.mode != "profession" or player["ready"]:
            return
        if role not in {"tank", "mage", "sniper", "necromancer", "weaponmaster", "paladin"}:
            return
        now = now or time.monotonic()
        player["effects"].clear()
        player["minions"].clear()
        player["last_shot"] = 0
        if "input" in player:
            player["input"].update(up=False, down=False, left=False, right=False, move_x=0, move_y=0, shoot=False, ability=False)
        player["role"] = role
        player["max_hp"] = self.test_settings["player_hp"] * (3 if role == "tank" else 1)
        player["next_weapon"] = now + 20 if role == "weaponmaster" else 0
        player["ability_ready"] = now
        player["ready"] = True
        self.spawn(player)

    def activate_paladin(self, player, now):
        if player.get("role") != "paladin" or not player.get("ready") or player["hp"] <= 0:
            return False
        if now < player.get("ability_ready", 0):
            return False
        player["effects"]["invincible"] = now + 7
        player["effects"]["speed"] = max(player["effects"].get("speed", 0), now + 7)
        player["ability_ready"] = now + 20
        return True

    def infected_melee(self, player, now, damage, reach, cleave=False):
        angle = finite_number(player.get("input", {}).get("angle"), 0)
        candidates = []
        for target in self.humans():
            if target.get("infected") or target.get("hp", 0) <= 0:
                continue
            offset_x, offset_y = target["x"] - player["x"], target["y"] - player["y"]
            distance = math.hypot(offset_x, offset_y)
            if distance > reach + PLAYER_RADIUS:
                continue
            if not cleave and distance > 0:
                target_angle = math.atan2(offset_y, offset_x)
                difference = abs(math.atan2(math.sin(target_angle - angle), math.cos(target_angle - angle)))
                if difference > .85:
                    continue
            candidates.append((distance, target))
        targets = [target for _, target in candidates] if cleave else [min(candidates, key=lambda item: item[0])[1]] if candidates else []
        for target in targets:
            self.damage(target, damage, player["id"], now)
        effect_x = player["x"] + math.cos(angle) * min(reach * .55, 70)
        effect_y = player["y"] + math.sin(angle) * min(reach * .55, 70)
        self.explosions.append({"x": effect_x, "y": effect_y, "radius": reach * (.9 if cleave else .55),
                                "color": "#9cff57", "life": .16, "magic": True})
        return bool(targets)

    def activate_infected_ability(self, player, now):
        if self.mode != "bio" or not player.get("infected") or player.get("choosing_zombie") or player.get("hp", 0) <= 0:
            return False
        form = player.get("zombie_form")
        if form not in INFECTED_ABILITY_COOLDOWNS or now < player.get("ability_ready", 0):
            return False
        angle = finite_number(player.get("input", {}).get("angle"), 0)
        dx, dy = math.cos(angle), math.sin(angle)
        stats = BOSS_STATS.get(form) or INFECTED_FORM_STATS.get(form)

        def infected_projectile(shot_angle, damage, speed=650, kind="infected", radius=8, life=2.4):
            self.add_bullet({"x": player["x"], "y": player["y"],
                             "vx": math.cos(shot_angle) * speed, "vy": math.sin(shot_angle) * speed,
                             "owner": player["id"], "color": "#9cff57", "damage": damage,
                             "damage_type": "normal", "radius": radius, "kind": kind,
                             "bounces": 0, "life": life, "created": now})

        if form == "normal":
            player["effects"]["infected_frenzy"] = now + 5
        elif form == "raider":
            player["effects"]["invincible"] = max(player["effects"].get("invincible", 0), now + .8)
            for _ in range(12):
                self.move_player(player, dx * 24, dy * 24)
        elif form == "shooter":
            for offset in (-.3, -.2, -.1, 0, .1, .2, .3):
                infected_projectile(angle + offset, stats["damage"] * 1.25, speed=720)
        elif form == "giant":
            for target in self.humans():
                if not target.get("infected") and target.get("hp", 0) > 0 and math.hypot(target["x"] - player["x"], target["y"] - player["y"]) <= 190:
                    self.damage(target, 55, player["id"], now)
            self.explosions.append({"x": player["x"], "y": player["y"], "radius": 190,
                                    "color": "#9cff57", "life": .35, "magic": True})
        elif form == "vomiter":
            self.create_pollution(player["x"] + dx * 190, player["y"] + dy * 190, now,
                                  max(2, self.wave // 5 + 1))
        elif form == "plague_lord":
            tier = max(1, self.wave // 5)
            for offset in (0, math.tau / 3, math.tau * 2 / 3):
                self.create_pollution(player["x"] + math.cos(offset) * 210,
                                      player["y"] + math.sin(offset) * 210, now, tier + 2)
        elif form == "brood_queen":
            summon_count = min(8, 3 + max(1, self.wave // 5))
            for index in range(summon_count):
                summon_kind = "raider" if index % 2 else "runner"
                radius = ZOMBIE_STATS[summon_kind]["radius"]
                position = self.nearby_zombie_spawn_position(player["x"], player["y"], radius, index)
                self.spawn_zombie(summon_kind, now, position=position)
            self.explosions.append({"x": player["x"], "y": player["y"], "radius": 175,
                                    "color": "#ff5ab7", "life": .55, "magic": True})
        elif form == "iron_abomination":
            player["effects"]["invincible"] = max(player["effects"].get("invincible", 0), now + 2.5)
            for _ in range(14):
                self.move_player(player, dx * 24, dy * 24)
            for target in self.humans():
                if not target.get("infected") and target.get("hp", 0) > 0 and math.hypot(target["x"] - player["x"], target["y"] - player["y"]) <= 240:
                    self.damage(target, 75, player["id"], now)
            self.explosions.append({"x": player["x"], "y": player["y"], "radius": 240,
                                    "color": "#c8ff84", "life": .4, "magic": True})
        player["ability_ready"] = now + INFECTED_ABILITY_COOLDOWNS[form]
        return True

    def move_player(self, player, dx, dy):
        next_x = clamp(player["x"] + dx, PLAYER_RADIUS, self.width - PLAYER_RADIUS)
        if not any(circle_hits_rect(next_x, player["y"], PLAYER_RADIUS, obstacle) for obstacle in self.active_terrain()):
            player["x"] = next_x
        next_y = clamp(player["y"] + dy, PLAYER_RADIUS, self.height - PLAYER_RADIUS)
        if not any(circle_hits_rect(player["x"], next_y, PLAYER_RADIUS, obstacle) for obstacle in self.active_terrain()):
            player["y"] = next_y

    def add_minion(self, player, movement="orbit"):
        player.setdefault("minions", []).append({"id": self.next_minion_id,
                                                   "hp": player.get("max_hp", 100) / 3,
                                                   "max_hp": player.get("max_hp", 100) / 3,
                                                   "angle": random.random() * math.tau, "movement": movement,
                                                   "x": player["x"], "y": player["y"], "last_shot": 0})
        self.next_minion_id += 1

    def damage(self, target, amount, owner_id, now, damage_type="normal"):
        if target["hp"] <= 0:
            return
        if target.get("upgrade_choices"):
            return
        if target["effects"].get("invincible", 0) > now:
            return
        if target["effects"].get("shield", 0) > now:
            amount *= 0.25 if damage_type == "laser" else 0.5
        if self.mode == "bio" and target.get("last_survivor") and not target.get("infected"):
            amount *= 0.5
        target["hp"] -= amount
        if target["hp"] <= 0:
            target["hp"] = 0
            target["respawn"] = math.inf if self.mode == "bio" else now + 2.5
            if self.mode == "bio" and target.get("infected"):
                remaining = max(0, int(target.get("zombie_respawns", 0)))
                target["choosing_zombie"] = remaining > 0
                target["zombie_respawns"] = max(0, remaining - 1) if remaining > 0 else 0
                target["zombie_form"] = None
                target["input"].update(up=False, down=False, left=False, right=False,
                                       move_x=0, move_y=0, shoot=False, ability=False)
            elif self.mode == "bio":
                self.rescue_progress[target["id"]] = 0
            owner = self.players.get(owner_id)
            if owner:
                owner["score"] += 1
                if self.mode == "upgrade":
                    owner["xp"] = owner.get("xp", 0) + 1
                elif self.mode == "bio" and target.get("infected") and not owner.get("infected"):
                    owner["xp"] = owner.get("xp", 0) + 3
                if owner.get("role") == "necromancer":
                    self.add_minion(owner, "roam")
                if not owner.get("infected"):
                    self.check_level_up(owner)
            if self.mode == "profession":
                target["ready"] = False
                target["role"] = None
                target["max_hp"] = 100
                target["effects"].clear()
                target["minions"] = []
                target["next_weapon"] = 0
                target["ability_ready"] = 0
                target["master_weapon"] = None
                if "input" in target:
                    target["input"].update(up=False, down=False, left=False, right=False, move_x=0, move_y=0, shoot=False, ability=False)

    def update_rescues(self, dt):
        if self.mode != "bio":
            return
        dead_players = [player for player in self.humans() if player["ready"] and player["hp"] <= 0 and not player.get("infected")]
        dead_ids = {player["id"] for player in dead_players}
        self.rescue_progress = {player_id: progress for player_id, progress in self.rescue_progress.items()
                                if player_id in dead_ids}
        if not self.rescue_enabled:
            self.rescue_progress.clear()
            return
        rescuers = [player for player in self.humans() if player["ready"] and player["hp"] > 0 and not player.get("infected")]
        for target in dead_players:
            nearby = any(player["id"] != target["id"] and
                         math.hypot(player["x"] - target["x"], player["y"] - target["y"]) <= 54
                         for player in rescuers)
            progress = self.rescue_progress.get(target["id"], 0)
            progress = min(10, progress + dt) if nearby else 0
            if progress < 10:
                self.rescue_progress[target["id"]] = progress
                continue
            target["hp"] = max(1, target["max_hp"] * .25)
            target["respawn"] = 0
            target["input"].update(up=False, down=False, left=False, right=False,
                                   move_x=0, move_y=0, shoot=False, ability=False)
            self.rescue_progress.pop(target["id"], None)

    def apply_pickup(self, player, kind, now):
        if kind == "health":
            player["hp"] = min(player.get("max_hp", 100), player["hp"] + player.get("max_hp", 100) * 0.25)
        elif kind == "minion":
            self.add_minion(player)
        else:
            player["effects"][kind] = now + self.test_settings["weapon_duration"]

    def explode_cannon(self, bullet, now):
        radius = 115
        self.explosions.append({"x": bullet["x"], "y": bullet["y"], "radius": radius,
                                "color": bullet["color"], "life": 0.35})
        if self.mode == "bio":
            for zombie in self.zombies:
                if zombie["hp"] > 0 and math.hypot(zombie["x"] - bullet["x"], zombie["y"] - bullet["y"]) < radius + zombie["radius"]:
                    self.damage_zombie(zombie, bullet["damage"], bullet["owner"], now)
            for player in self.humans():
                if player.get("infected") and player["hp"] > 0 and math.hypot(player["x"] - bullet["x"], player["y"] - bullet["y"]) < radius + PLAYER_RADIUS:
                    self.damage(player, bullet["damage"], bullet["owner"], now, "explosive")
        else:
            for player in self.players.values():
                if player["id"] != bullet["owner"] and player["hp"] > 0:
                    distance = math.hypot(player["x"] - bullet["x"], player["y"] - bullet["y"])
                    if distance < radius + PLAYER_RADIUS:
                        self.damage(player, 70, bullet["owner"], now, "explosive")
                for minion in player.get("minions", []):
                    if player["id"] != bullet["owner"] and math.hypot(minion["x"] - bullet["x"], minion["y"] - bullet["y"]) < radius + 12:
                        minion["hp"] -= 70
        for block in self.terrain:
            if block["active"] and circle_hits_rect(bullet["x"], bullet["y"], radius, block):
                block["active"], block["restore"] = False, now + 5

    def explode_magic(self, bullet, now):
        radius = 78
        self.explosions.append({"x": bullet["x"], "y": bullet["y"], "radius": radius,
                                "color": bullet["color"], "life": 0.25, "magic": True})
        for player in self.players.values():
            if player["id"] != bullet["owner"] and player["hp"] > 0 and math.hypot(player["x"] - bullet["x"], player["y"] - bullet["y"]) < radius + PLAYER_RADIUS:
                self.damage(player, 37.5, bullet["owner"], now)
            if player["id"] != bullet["owner"]:
                for minion in player.get("minions", []):
                    if math.hypot(minion["x"] - bullet["x"], minion["y"] - bullet["y"]) < radius + 12:
                        minion["hp"] -= 37.5

    def update_minions(self, dt, now):
        for owner in self.players.values():
            minions = [minion for minion in owner.get("minions", []) if minion["hp"] > 0]
            owner["minions"] = minions
            for index, minion in enumerate(minions):
                minion["angle"] += dt * (1.45 + (index % 2) * 0.15)
                if minion.get("movement") != "roam":
                    orbit = 58 + (index // 6) * 28
                    minion["x"] = owner["x"] + math.cos(minion["angle"] + index * math.tau / max(1, len(minions))) * orbit
                    minion["y"] = owner["y"] + math.sin(minion["angle"] + index * math.tau / max(1, len(minions))) * orbit
                if self.mode == "bio":
                    enemies = [zombie for zombie in self.zombies if zombie["hp"] > 0]
                    enemies.extend(p for p in self.players.values()
                                   if p["id"] != owner["id"] and p["hp"] > 0 and p.get("infected"))
                else:
                    enemies = [p for p in self.players.values()
                               if p["id"] != owner["id"] and p["hp"] > 0]
                if not enemies:
                    continue
                target = min(enemies, key=lambda p: math.hypot(p["x"] - minion["x"], p["y"] - minion["y"]))
                distance = math.hypot(target["x"] - minion["x"], target["y"] - minion["y"])
                if minion.get("movement") == "roam":
                    if distance > 170:
                        minion["x"] += (target["x"] - minion["x"]) / distance * 135 * dt
                        minion["y"] += (target["y"] - minion["y"]) / distance * 135 * dt
                if owner["hp"] <= 0 or now - minion["last_shot"] < 0.75:
                    continue
                distance = math.hypot(target["x"] - minion["x"], target["y"] - minion["y"])
                if distance > 650:
                    continue
                minion["last_shot"] = now
                angle = math.atan2(target["y"] - minion["y"], target["x"] - minion["x"])
                self.add_bullet({"x": minion["x"], "y": minion["y"], "vx": math.cos(angle) * 620,
                                 "vy": math.sin(angle) * 620, "owner": owner["id"], "color": owner["color"],
                                 "damage": 10, "damage_type": "normal", "radius": 5, "kind": "minion",
                                 "bounces": 0, "life": 2.2, "created": now})

    def advance_bullet(self, bullet, dt):
        old_x, old_y = bullet["x"], bullet["y"]
        radius = bullet.get("radius", 6)
        speed = math.hypot(bullet["vx"], bullet["vy"])
        if speed == 0:
            return True
        dx, dy, travel = bullet["vx"] / speed, bullet["vy"] / speed, speed * dt
        candidates = []
        if dx > 0:
            candidates.append(((self.width - radius - old_x) / dx, (-1, 0)))
        elif dx < 0:
            candidates.append(((radius - old_x) / dx, (1, 0)))
        if dy > 0:
            candidates.append(((self.height - radius - old_y) / dy, (0, -1)))
        elif dy < 0:
            candidates.append(((radius - old_y) / dy, (0, 1)))
        for obstacle in self.active_terrain():
            expanded = {"x": obstacle["x"] - radius, "y": obstacle["y"] - radius,
                        "w": obstacle["w"] + radius * 2, "h": obstacle["h"] + radius * 2}
            hit = ray_rect_hit(old_x, old_y, dx, dy, expanded)
            if hit:
                candidates.append(hit)
        distance, normal = min((hit for hit in candidates if hit[0] > 0.01), key=lambda hit: hit[0])
        if distance > travel:
            bullet["x"], bullet["y"] = old_x + dx * travel, old_y + dy * travel
            return True
        bullet["x"], bullet["y"] = old_x + dx * distance, old_y + dy * distance
        if bullet["bounces"] <= 0:
            return False
        dot = bullet["vx"] * normal[0] + bullet["vy"] * normal[1]
        bullet["vx"] -= 2 * dot * normal[0]
        bullet["vy"] -= 2 * dot * normal[1]
        bullet["bounces"] -= 1
        remaining = max(0, travel - distance)
        bullet["x"] = clamp(bullet["x"] + bullet["vx"] / speed * (remaining + 0.1), radius, self.width - radius)
        bullet["y"] = clamp(bullet["y"] + bullet["vy"] / speed * (remaining + 0.1), radius, self.height - radius)
        return True

    def fire_laser(self, player, angle, now, damage, beam=False):
        dx, dy = math.cos(angle), math.sin(angle)
        start_x, start_y, damaged = player["x"], player["y"], set()
        for segment in range(4):  # 初始光束 + 最多三次反射
            candidates = []
            if dx > 0:
                candidates.append(((self.width - start_x) / dx, (-1, 0)))
            elif dx < 0:
                candidates.append(((0 - start_x) / dx, (1, 0)))
            if dy > 0:
                candidates.append(((self.height - start_y) / dy, (0, -1)))
            elif dy < 0:
                candidates.append(((0 - start_y) / dy, (0, 1)))
            for obstacle in self.active_terrain():
                hit = ray_rect_hit(start_x, start_y, dx, dy, obstacle)
                if hit:
                    candidates.append(hit)
            distance, normal = min((hit for hit in candidates if hit[0] > 0.01), key=lambda hit: hit[0])
            end_x, end_y = start_x + dx * distance, start_y + dy * distance
            for zombie in self.zombies if self.mode == "bio" else ():
                marker = f"z{zombie['id']}"
                if marker in damaged or zombie["hp"] <= 0:
                    continue
                along = (zombie["x"] - start_x) * dx + (zombie["y"] - start_y) * dy
                side = abs((zombie["x"] - start_x) * dy - (zombie["y"] - start_y) * dx)
                if 0 < along < distance and side < zombie["radius"] + 7:
                    damaged.add(marker)
                    self.damage_zombie(zombie, damage, player["id"], now)
            laser_targets = (self.players.values() if self.mode != "bio" else
                             (target for target in self.players.values() if target.get("infected")))
            for target in laser_targets:
                if target["id"] == player["id"] or target["id"] in damaged or target["hp"] <= 0:
                    continue
                along = (target["x"] - start_x) * dx + (target["y"] - start_y) * dy
                side = abs((target["x"] - start_x) * dy - (target["y"] - start_y) * dx)
                if 0 < along < distance and side < PLAYER_RADIUS + 7:
                    damaged.add(target["id"])
                    self.damage(target, damage, player["id"], now, "laser")
            for owner in self.players.values():
                if owner["id"] == player["id"]:
                    continue
                for minion in owner.get("minions", []):
                    marker = f"m{owner['id']}:{minion['id']}"
                    if marker in damaged or minion["hp"] <= 0:
                        continue
                    along = (minion["x"] - start_x) * dx + (minion["y"] - start_y) * dy
                    side = abs((minion["x"] - start_x) * dy - (minion["y"] - start_y) * dx)
                    if 0 < along < distance and side < 19:
                        damaged.add(marker)
                        minion["hp"] -= damage
            self.lasers.append({"x1": start_x, "y1": start_y, "x2": end_x, "y2": end_y,
                                "owner": player["id"], "segment": segment, "created": now,
                                "color": player["color"], "life": 0.16, "beam": beam})
            dot = dx * normal[0] + dy * normal[1]
            dx, dy = dx - 2 * dot * normal[0], dy - 2 * dot * normal[1]
            start_x, start_y = end_x + dx * 0.2, end_y + dy * 0.2

    async def loop(self):
        while self.code in rooms:
            started = time.monotonic()
            dt = min(started - self.last, 0.05)
            self.last = started
            self.update(dt, started)
            if started - self.last_broadcast >= 1 / NETWORK_RATE:
                self.last_broadcast = started
                await self.broadcast()
            await asyncio.sleep(max(0, 1 / TICK_RATE - (time.monotonic() - started)))

    def update(self, dt, now):
        self.restore_terrain(now)
        self.update_bots(now)
        self.update_last_survivor(now)
        self.update_zombies(dt, now)
        self.update_hazards(dt, now)
        for p in self.players.values():
            if not p["ready"] or p.get("choosing_zombie"):
                continue
            if p["hp"] <= 0:
                if self.mode != "bio" and now >= p["respawn"]:
                    self.spawn(p)
                continue
            # 客户端输入由独立定时器续传；保留更宽松的网络容错，避免低帧率时移动和连射被误判为松开。
            if not p.get("is_bot") and now - p.get("last_input", now) > 4:
                p["input"].update(up=False, down=False, left=False, right=False,
                                  move_x=0, move_y=0, shoot=False, ability=False)
            dx = p["input"].get("move_x", p["input"]["right"] - p["input"]["left"])
            dy = p["input"].get("move_y", p["input"]["down"] - p["input"]["up"])
            length = math.hypot(dx, dy)
            if length > 1:
                dx, dy = dx / length, dy / length
            upgrade_ranks = p.get("upgrades", {}) if self.mode in {"upgrade", "bio"} else {}
            infected_stats = (BOSS_STATS.get(p.get("zombie_form")) or INFECTED_FORM_STATS.get(p.get("zombie_form"))) if p.get("infected") else None
            agility_bonus = min(.8, .05 * upgrade_ranks.get("agility", 0)) if self.mode == "bio" else .06 * upgrade_ranks.get("agility", 0)
            speed = (infected_stats.get("speed", 80) * (2.2 if p.get("zombie_form") in BOSS_STATS else 1) if infected_stats else PLAYER_SPEED)
            speed *= (1.45 if p["effects"].get("speed", 0) > now else 1) * (1 + agility_bonus)
            if p["effects"].get("infected_frenzy", 0) > now:
                speed *= 1.45
            if p.get("last_survivor") and not p.get("infected"):
                speed *= 1.35
            self.move_player(p, dx * speed * dt, dy * speed * dt)
            rapid = p["effects"].get("rapid", 0) > now
            cannon = p["effects"].get("cannon", 0) > now
            laser = p["effects"].get("laser", 0) > now
            beam = p["effects"].get("beam", 0) > now and not laser and not cannon
            role = p.get("role")
            if role == "weaponmaster" and now >= p.get("next_weapon", math.inf):
                previous = p.get("master_weapon")
                if previous:
                    p["effects"].pop(previous, None)
                weapon = random.choice(WEAPON_MASTER_WEAPONS)
                p["master_weapon"] = weapon
                p["effects"][weapon] = now + 10
                p["next_weapon"] = now + 20
                cannon = weapon == "cannon"
                laser = weapon == "laser"
                beam = weapon == "beam"
            if p["input"].get("ability"):
                if p.get("infected"):
                    self.activate_infected_ability(p, now)
                elif role == "paladin":
                    self.activate_paladin(p, now)
            cooldown = infected_stats.get("cooldown", .65) if infected_stats else 1.25 if cannon else 0.09 if beam else 0.55 if laser else 0.5 if role == "mage" else 0.7 if role == "sniper" else 0.11 if rapid else 0.24
            cooldown *= max(.32, .9 ** upgrade_ranks.get("haste", 0)) if self.mode == "bio" else .9 ** upgrade_ranks.get("haste", 0)
            if p.get("last_survivor") and not p.get("infected"):
                cooldown *= .4
            if (p["input"]["shoot"] or p.get("shot_queued", False)) and now - p["last_shot"] >= cooldown:
                p["shot_queued"] = False
                p["last_shot"] = now
                angle = p["input"]["angle"]
                if infected_stats:
                    form = p.get("zombie_form")
                    infected_damage = infected_stats["damage"] * (1.5 if p["effects"].get("infected_frenzy", 0) > now else 1)
                    if form in {"normal", "raider"}:
                        self.infected_melee(p, now, infected_damage, 95 if form == "normal" else 82)
                    elif form == "giant":
                        self.infected_melee(p, now, infected_damage, 145, cleave=True)
                    elif form == "iron_abomination":
                        self.infected_melee(p, now, infected_damage, 175, cleave=True)
                    else:
                        projectile_kind = "infected_vomit" if form in {"vomiter", "plague_lord"} else "infected"
                        count = 5 if form == "plague_lord" else 3 if form == "brood_queen" else 1
                        spread = .18
                        for index in range(count):
                            shot_angle = angle + (index - (count - 1) / 2) * spread
                            projectile_speed = 390 if projectile_kind == "infected_vomit" else 680 if form == "shooter" else 560
                            self.add_bullet({"x": p["x"], "y": p["y"], "vx": math.cos(shot_angle) * projectile_speed,
                                             "vy": math.sin(shot_angle) * projectile_speed,
                                             "owner": p["id"], "color": "#9cff57", "damage": infected_damage,
                                             "damage_type": "normal", "radius": 10 if projectile_kind == "infected_vomit" else 7,
                                             "kind": projectile_kind, "bounces": 0, "life": 3, "created": now})
                elif cannon:
                    cannon_damage_multiplier = (1.6 if p["effects"].get("damage", 0) > now else 1) * (1 + (.09 if self.mode == "bio" else .1) * upgrade_ranks.get("power", 0))
                    self.add_bullet({"x": p["x"], "y": p["y"],
                                     "vx": math.cos(angle) * 430, "vy": math.sin(angle) * 430,
                                     "owner": p["id"], "color": p["color"], "damage": self.test_settings["cannon_damage"] * cannon_damage_multiplier * (5 if self.mode == "bio" else 1) * (1.6 if p.get("last_survivor") else 1),
                                     "damage_type": "explosive", "radius": 18, "kind": "cannon",
                                     "bounces": 0, "life": 3, "created": now})
                elif laser:
                    self.fire_laser(p, angle, now, self.test_settings["laser_damage"] * (1.6 if self.mode == "bio" else 1) * (1.6 if p.get("last_survivor") else 1))
                elif beam:
                    self.fire_laser(p, angle, now, self.test_settings["beam_damage"] * (1.5 if self.mode == "bio" else 1) * (1.6 if p.get("last_survivor") else 1), beam=True)
                else:
                    arsenal_rank = upgrade_ranks.get("arsenal", 0)
                    angles = ((angle - 0.16, angle, angle + 0.16) if p["effects"].get("multishot", 0) > now else
                              (angle - .08, angle + .08) if arsenal_rank == 1 else
                              (angle - .13, angle, angle + .13) if arsenal_rank >= 2 else (angle,))
                    base_damage = self.test_settings["bullet_damage"]
                    damage = (base_damage * 1.6 if p["effects"].get("damage", 0) > now else base_damage) * (1 + (.09 if self.mode == "bio" else .1) * upgrade_ranks.get("power", 0))
                    if p.get("last_survivor") and not p.get("infected"):
                        damage *= 1.6
                    if arsenal_rank:
                        damage *= .82 if arsenal_rank == 1 else .72
                    for shot_angle in angles:
                        bullet_kind = "mage" if role == "mage" else "sniper" if role == "sniper" else "bullet"
                        bullet_damage = 37.5 if role == "mage" else 75 if role == "sniper" else damage
                        velocity_bonus = min(1.2, .075 * upgrade_ranks.get("velocity", 0)) if self.mode == "bio" else .1 * upgrade_ranks.get("velocity", 0)
                        bullet_speed = (1200 if role == "sniper" else 700 if role == "mage" else BULLET_SPEED) * (1 + velocity_bonus)
                        bullet_radius = 9 if role == "mage" else 5 if role == "sniper" else 6
                        self.add_bullet({"x": p["x"], "y": p["y"],
                                         "vx": math.cos(shot_angle) * bullet_speed,
                                         "vy": math.sin(shot_angle) * bullet_speed,
                                         "owner": p["id"], "color": p["color"], "damage": bullet_damage,
                                         "damage_type": "normal", "radius": bullet_radius, "kind": bullet_kind,
                                         "bounces": 3 if p["effects"].get("ricochet", 0) > now else 0,
                                         "life": 2.5, "created": now})

            for pickup in self.pickups if not p.get("infected") else ():
                if pickup["active"] and math.hypot(p["x"] - pickup["x"], p["y"] - pickup["y"]) < 45:
                    self.apply_pickup(p, pickup["kind"], now)
                    pickup["active"] = False

        self.update_rescues(dt)
        self.sync_pickups()
        self.update_minions(dt, now)

        alive = []
        for b in self.bullets:
            b["life"] -= dt
            if b["life"] <= 0:
                if b["kind"] == "cannon":
                    self.explode_cannon(b, now)
                elif b["kind"] in {"vomit", "infected_vomit"}:
                    self.create_pollution(b["x"], b["y"], now, max(1, self.wave // 5))
                continue
            previous_x, previous_y = b["x"], b["y"]
            hit = not self.advance_bullet(b, dt)
            if hit and b["kind"] == "cannon":
                self.explode_cannon(b, now)
            elif hit and b["kind"] == "mage":
                self.explode_magic(b, now)
            hostile_bio_projectile = b["kind"] in {"zombie", "vomit", "infected", "infected_vomit"}
            if not hit:
                if self.mode == "bio" and not hostile_bio_projectile:
                    zombie = next((zombie for zombie in self.zombies if zombie["hp"] > 0 and
                                   segment_hits_circle(previous_x, previous_y, b["x"], b["y"], zombie["x"], zombie["y"], zombie["radius"] + b["radius"])), None)
                    if zombie:
                        if b["kind"] == "cannon":
                            self.explode_cannon(b, now)
                        else:
                            self.damage_zombie(zombie, b["damage"], b["owner"], now)
                        hit = True
                    if not hit:
                        infected_target = next((player for player in self.humans() if player.get("infected") and player["hp"] > 0 and
                                                segment_hits_circle(previous_x, previous_y, b["x"], b["y"], player["x"], player["y"], PLAYER_RADIUS + b["radius"])), None)
                        if infected_target:
                            self.damage(infected_target, b["damage"], b["owner"], now, b["damage_type"])
                            hit = True
            if not hit and self.mode != "bio":
                for owner in self.players.values():
                    if owner["id"] == b["owner"]:
                        continue
                    minion = next((m for m in owner.get("minions", [])
                                   if m["hp"] > 0 and math.hypot(m["x"] - b["x"], m["y"] - b["y"]) < b["radius"] + 12), None)
                    if minion:
                        if b["kind"] == "cannon":
                            self.explode_cannon(b, now)
                        elif b["kind"] == "mage":
                            self.explode_magic(b, now)
                        else:
                            minion["hp"] -= b["damage"]
                        hit = True
                        break
            if hit:
                if b["kind"] in {"vomit", "infected_vomit"}:
                    self.create_pollution(b["x"], b["y"], now, max(1, self.wave // 5))
                continue
            for p in self.players.values() if self.mode != "bio" or hostile_bio_projectile else ():
                player_hit = (segment_hits_circle(previous_x, previous_y, b["x"], b["y"], p["x"], p["y"], PLAYER_RADIUS + b["radius"])
                              if self.mode == "bio" else math.hypot(p["x"] - b["x"], p["y"] - b["y"]) < PLAYER_RADIUS + b["radius"])
                if p["id"] != b["owner"] and p["hp"] > 0 and not p.get("infected") and player_hit:
                    if b["kind"] == "cannon":
                        self.explode_cannon(b, now)
                    elif b["kind"] == "mage":
                        self.explode_magic(b, now)
                    else:
                        self.damage(p, b["damage"], b["owner"], now, b["damage_type"])
                    hit = True
                    break
            if hit and b["kind"] in {"vomit", "infected_vomit"}:
                self.create_pollution(b["x"], b["y"], now, max(1, self.wave // 5))
            if not hit and b["life"] > 0 and 0 < b["x"] < self.width and 0 < b["y"] < self.height:
                alive.append(b)
        self.bullets = alive
        for laser in self.lasers:
            laser["life"] -= dt
        self.lasers = [laser for laser in self.lasers if laser["life"] > 0]
        for explosion in self.explosions:
            explosion["life"] -= dt
        self.explosions = [explosion for explosion in self.explosions if explosion["life"] > 0]

    async def broadcast(self):
        now = time.monotonic()
        payload = json.dumps({"type": "state", "server_time": round(now * 1000, 3),
                              "host_id": self.host_id, "test": self.test_settings, "players": [
            {**{k: p[k] for k in ("id", "name", "max_hp", "score", "color", "role", "ready")},
             "bot": p.get("is_bot", False),
             "bot_difficulty": "hard" if p.get("is_bot") else None,
             "level": p.get("level", 1), "xp": p.get("xp", p.get("score", 0)), "upgrades": p.get("upgrades", {}),
             "upgrade_choices": p.get("upgrade_choices", []),
             "upgrading": bool(p.get("upgrade_choices")),
             "next_level_score": self.next_level_xp(p.get("level", 1)) if self.mode == "bio" or p.get("level", 1) < 1 + sum(UPGRADE_MAX_RANKS.values()) else None,
             "x": round(p["x"], 1), "y": round(p["y"], 1), "hp": round(p["hp"], 1),
             "rescue_progress": round(self.rescue_progress.get(p["id"], 0), 1) if self.mode == "bio" else 0,
             "infection_progress": round(self.infection_progress.get(p["id"], 0), 1) if self.mode == "bio" else 0,
             "infected": p.get("infected", False), "choosing_zombie": p.get("choosing_zombie", False),
             "zombie_form": p.get("zombie_form"), "zombie_respawns": p.get("zombie_respawns", 0),
             "boss_used_wave": p.get("boss_used_wave", 0), "last_survivor": p.get("last_survivor", False),
             "input_seq": p.get("input_seq", -1),
             "move_x": round(p["input"].get("move_x", 0), 3), "move_y": round(p["input"].get("move_y", 0), 3),
             "effects": {kind: round(expires - now, 1) for kind, expires in p["effects"].items() if expires > now},
             "weapon_cooldown": max(0, round(p.get("next_weapon", 0) - now, 1)),
             "ability_cooldown": max(0, round(p.get("ability_ready", 0) - now, 1)),
             "minions": [{"id": m["id"], "x": round(m["x"], 1), "y": round(m["y"], 1),
                           "hp": round(m["hp"], 1), "max_hp": round(m["max_hp"], 1), "movement": m["movement"]}
                          for m in p.get("minions", [])]}
            for p in self.players.values()
        ], "bullets": [{"x": round(b["x"], 1), "y": round(b["y"], 1),
                          "vx": round(b["vx"], 1), "vy": round(b["vy"], 1),
                          "age": round(max(0, now - b.get("created", now)), 3),
                          **{k: b[k] for k in ("id", "owner", "color", "bounces", "radius", "kind")}} for b in self.bullets],
           "lasers": [{**{k: round(value, 1) if k in {"x1", "y1", "x2", "y2", "life"} else value
                           for k, value in laser.items() if k != "created"},
                       "age": round(max(0, now - laser.get("created", now)), 3)} for laser in self.lasers],
           "explosions": [{k: round(value, 1) if k in {"x", "y", "radius", "life"} else value
                            for k, value in explosion.items()} for explosion in self.explosions],
           "pickups": [p for p in self.pickups if p["active"]],
           "zombies": [{"id": zombie["id"], "kind": "normal" if zombie.get("disguised") and not zombie.get("revealed") else zombie["kind"], "boss": zombie["boss"],
                         "boss_name": zombie.get("boss_name"), "x": round(zombie["x"], 1), "y": round(zombie["y"], 1),
                         "hp": round(zombie["hp"], 1), "max_hp": zombie["max_hp"], "radius": zombie["radius"],
                         "move_x": round(zombie.get("move_x", 0), 3), "move_y": round(zombie.get("move_y", 0), 3)}
                        for zombie in self.zombies if zombie["hp"] > 0],
           "hazards": [{"id": hazard["id"], "x": round(hazard["x"], 1), "y": round(hazard["y"], 1),
                        "radius": round(hazard["radius"], 1), "life": round(max(0, hazard["expires"] - now), 1)}
                       for hazard in self.hazards],
           "bio": {"wave": self.wave, "active": self.wave_active,
                   "remaining": sum(1 for zombie in self.zombies if zombie["hp"] > 0) + len(self.pending_zombies),
                   "next_wave": max(0, round(self.next_wave - now, 1)) if not self.wave_active else 0,
                   "boss": next((zombie.get("boss_name") for zombie in self.zombies if zombie.get("boss") and zombie["hp"] > 0), None),
                   "host_id": self.host_id, "rescue_enabled": self.rescue_enabled,
                   "infected_players": sum(1 for player in self.humans() if player.get("infected")),
                   "survivor_players": sum(1 for player in self.humans() if not player.get("infected")),
                   "boss_tier": max(1, self.wave // 5) if self.wave >= 5 else 0} if self.mode == "bio" else None,
           "destroyed": [[block["id"], max(0, round(block["restore"] - now, 1))]
                         for block in self.terrain if not block["active"]]},
                         ensure_ascii=False, separators=(",", ":"))
        members = [(pid, player) for pid, player in self.players.items() if not player.get("is_bot")]
        results = await asyncio.gather(*(player["ws"].send_str(payload) for _, player in members),
                                       return_exceptions=True)
        for (pid, _), result in zip(members, results):
            if isinstance(result, BaseException):
                self.players.pop(pid, None)

    async def broadcast_chat(self, player, message):
        payload = {"type": "chat", "player_id": player["id"], "name": player["name"],
                   "color": player["color"], "message": message,
                   "level": player.get("level") if self.mode in {"upgrade", "bio"} else None}
        await asyncio.gather(*(member["ws"].send_json(payload) for member in self.humans()),
                             return_exceptions=True)


async def websocket(request):
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=4096)
    await ws.prepare(request)
    player = room = None
    try:
        first = await ws.receive_json(timeout=10)
        code = "".join(c for c in str(first.get("room", "PUBLIC")).upper() if c.isalnum())[:10] or "PUBLIC"
        mode = str(first.get("mode", "classic"))
        if mode not in {"classic", "items", "pure", "profession", "upgrade", "bio"}:
            mode = "classic"
        if code in rooms:
            room = rooms[code]
            if room.mode != mode:
                await ws.send_json({"type": "error", "message": "该房间已经使用其他玩法模式，请选择相同模式或更换房间号"})
                return ws
        else:
            room = Room(code, mode)
            rooms[code] = room
        if len(room.humans()) >= 12:
            await ws.send_json({"type": "error", "message": "房间已满（最多 12 人）"})
            return ws
        pid = secrets.token_hex(4)
        ready = mode != "profession"
        player = {"id": pid, "name": str(first.get("name", "玩家"))[:12] or "玩家", "x": 0, "y": 0,
                  "hp": 0, "max_hp": room.test_settings["player_hp"], "score": 0, "color": room.next_player_color(), "ws": ws, "is_bot": False, "last_shot": 0,
                  "respawn": 0, "effects": {}, "minions": [], "role": None, "ready": ready,
                  "infected": False, "choosing_zombie": False, "zombie_form": None, "zombie_respawns": 0, "boss_used_wave": 0,
                  "last_survivor": False,
                  "next_weapon": 0, "ability_ready": 0, "master_weapon": None, "last_chat": 0,
                  "level": 1, "xp": 0, "upgrades": {}, "upgrade_choices": [],
                  "last_input": time.monotonic(), "input_seq": -1,
                  "input": {"up": 0, "down": 0, "left": 0, "right": 0, "shoot": False, "ability": False, "angle": 0}}
        if ready:
            room.spawn(player)
        room.players[pid] = player
        if room.host_id is None or room.host_id not in room.players:
            room.host_id = pid
        room.sync_solo_bot()
        print_room_population(f"玩家 {player['name']} 加入 {code}")
        now = time.monotonic()
        await ws.send_json({"type": "welcome", "protocol": PROTOCOL_VERSION, "build": BUILD_VERSION, "edition": "internet", "network_rate": NETWORK_RATE,
                            "id": pid, "room": code, "mode": mode, "width": room.width, "height": room.height,
                            "obstacles": [{**{k: block[k] for k in ("id", "x", "y", "w", "h", "active")},
                                           "restore": max(0, round(block["restore"] - now, 1))}
                                          for block in room.terrain]})
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("type") == "input":
                    sequence = int(finite_number(data.get("seq"), player.get("input_seq", -1) + 1))
                    if sequence <= player.get("input_seq", -1):
                        continue
                    player["input_seq"] = sequence
                    inp = player["input"]
                    was_shooting = inp.get("shoot", False)
                    for key in ("up", "down", "left", "right", "shoot", "ability"):
                        inp[key] = bool(data.get(key))
                    if inp["shoot"] and not was_shooting:
                        player["shot_queued"] = True
                    move_x = finite_number(data.get("move_x"), inp["right"] - inp["left"])
                    move_y = finite_number(data.get("move_y"), inp["down"] - inp["up"])
                    move_length = math.hypot(move_x, move_y)
                    if not math.isfinite(move_length):
                        move_x = move_y = 0
                    elif move_length > 1:
                        move_x, move_y = move_x / move_length, move_y / move_length
                    angle = finite_number(data.get("angle"))
                    inp["move_x"], inp["move_y"] = move_x, move_y
                    inp["angle"] = angle
                    player["last_input"] = time.monotonic()
                elif data.get("type") == "select_role":
                    room.select_role(player, str(data.get("role", "")), time.monotonic())
                elif data.get("type") == "select_upgrade":
                    choice = str(data.get("upgrade", ""))
                    if choice in player.get("upgrade_choices", []):
                        room.apply_upgrade(player, choice)
                elif data.get("type") == "select_zombie":
                    room.select_zombie_form(player, str(data.get("form", "")))
                elif data.get("type") == "ability":
                    now = time.monotonic()
                    if player.get("infected"):
                        room.activate_infected_ability(player, now)
                    else:
                        room.activate_paladin(player, now)
                elif data.get("type") == "toggle_rescue":
                    if room.mode == "bio" and room.host_id == player["id"]:
                        room.rescue_enabled = bool(data.get("enabled"))
                        if not room.rescue_enabled:
                            room.rescue_progress.clear()
                elif data.get("type") == "test_settings":
                    if room.host_id == player["id"] and isinstance(data.get("values"), dict):
                        room.apply_test_settings(data["values"])
                elif data.get("type") == "test_infect_self":
                    if room.mode == "bio" and room.host_id == player["id"] and not player.get("infected"):
                        room.infect_player(player)
                elif data.get("type") == "chat":
                    now = time.monotonic()
                    message = " ".join(str(data.get("message", "")).split())[:CHAT_MAX_LENGTH]
                    if message and now - player["last_chat"] >= CHAT_COOLDOWN:
                        player["last_chat"] = now
                        await room.broadcast_chat(player, message)
                elif data.get("type") == "ping":
                    await ws.send_json({"type": "pong", "sent": data.get("sent")})
            elif msg.type == WSMsgType.ERROR:
                break
    except (asyncio.TimeoutError, json.JSONDecodeError, TypeError, ValueError):
        pass
    finally:
        if room and player:
            room.players.pop(player["id"], None)
            room.rescue_progress.pop(player["id"], None)
            if room.host_id == player["id"]:
                room.host_id = next((member["id"] for member in room.humans()), None)
            room.sync_solo_bot()
            if not room.humans():
                rooms.pop(room.code, None)
                room.task.cancel()
            print_room_population(f"玩家 {player['name']} 离开 {room.code}")
    return ws


async def index(_):
    return web.FileResponse(ROOT / "public" / "index.html")


async def health(_):
    return web.json_response({"game": "neon-brawl", "edition": "internet", "status": "ok", "protocol": PROTOCOL_VERSION, "build": BUILD_VERSION})


async def room_list(_):
    public_rooms = []
    for code, room in sorted(rooms.items()):
        human_count = len(room.humans())
        if not human_count:
            continue
        public_rooms.append({"code": code, "mode": room.mode, "players": human_count,
                             "infected": sum(1 for player in room.humans() if player.get("infected")),
                             "bots": len(room.bots()), "capacity": 12})
    return web.json_response({"rooms": public_rooms})


@web.middleware
async def prevent_stale_client_cache(request, handler):
    response = await handler(request)
    if request.path == "/" or request.path.endswith((".js", ".css")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app = web.Application(middlewares=[prevent_stale_client_cache])
app.router.add_get("/", index)
app.router.add_get("/health", health)
app.router.add_get("/rooms", room_list)
app.router.add_get("/ws", websocket)
app.router.add_static("/static", ROOT / "public")

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
