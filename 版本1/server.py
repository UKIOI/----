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
BUILD_VERSION = 43
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
ZOMBIE_STATS = {
    "normal": {"hp": 65, "speed": 105, "damage": 12, "radius": 21, "xp": 1},
    "shooter": {"hp": 55, "speed": 78, "damage": 10, "radius": 20, "xp": 2},
    "giant": {"hp": 250, "speed": 58, "damage": 28, "radius": 35, "xp": 4},
    "runner": {"hp": 38, "speed": 195, "damage": 8, "radius": 14, "xp": 1},
}
BOSS_STATS = {
    "plague_lord": {"name": "瘟疫领主", "hp": 1200, "speed": 72, "damage": 16, "radius": 48, "xp": 14},
    "brood_queen": {"name": "巢群女王", "hp": 1050, "speed": 85, "damage": 18, "radius": 44, "xp": 14},
    "iron_abomination": {"name": "钢铁畸变体", "hp": 1550, "speed": 62, "damage": 34, "radius": 55, "xp": 18},
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
            occupied = any(p["hp"] > 0 and circle_hits_rect(p["x"], p["y"], PLAYER_RADIUS, block)
                           for p in self.players.values())
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
        steps = max(1, math.ceil(distance / 24))
        terrain = list(self.active_terrain())
        for step in range(1, steps + 1):
            ratio = step / steps
            x = start_x + (end_x - start_x) * ratio
            y = start_y + (end_y - start_y) * ratio
            if any(circle_hits_rect(x, y, radius, obstacle) for obstacle in terrain):
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
            if any(circle_hits_rect(x, y, radius + 3, wall) for wall in self.active_terrain()):
                continue
            if players and min(math.hypot(player["x"] - x, player["y"] - y) for player in players) < 520:
                continue
            return x, y
        return self.random_open_position(radius + 5)

    def spawn_zombie(self, kind, now, boss_kind=None):
        humans = max(1, len(self.humans()))
        stats = BOSS_STATS[boss_kind] if boss_kind else ZOMBIE_STATS[kind]
        health_scale = (1 + max(0, self.wave - 1) * .1) * (1 + max(0, humans - 1) * .2)
        damage_scale = (1 + max(0, self.wave - 1) * .045) * (1 + max(0, humans - 1) * .08)
        radius = stats["radius"]
        x, y = self.zombie_spawn_position(radius)
        zombie = {"id": self.next_zombie_id, "kind": boss_kind or kind, "boss": bool(boss_kind),
                  "boss_name": stats.get("name"), "x": x, "y": y, "radius": radius,
                  "hp": round(stats["hp"] * health_scale), "max_hp": round(stats["hp"] * health_scale),
                  "speed": stats["speed"], "damage": stats["damage"] * damage_scale, "xp": stats["xp"],
                  "last_attack": 0, "last_shot": 0, "next_think": 0, "next_special": now + 3,
                  "move_x": 0, "move_y": 0, "charge_until": 0}
        self.next_zombie_id += 1
        self.zombies.append(zombie)
        return zombie

    def start_bio_wave(self, now):
        self.wave += 1
        humans = max(1, len(self.humans()))
        count = min(48, math.ceil((4 + self.wave * 1.55) * (.72 + humans * .48)))
        choices = ["normal"] * 7
        if self.wave >= 2:
            choices += ["runner"] * 3
        if self.wave >= 3:
            choices += ["shooter"] * 3
        if self.wave >= 4:
            choices += ["giant"] * 2
        for _ in range(count):
            self.spawn_zombie(random.choice(choices), now)
        if self.wave % 5 == 0:
            self.spawn_zombie("boss", now, random.choice(tuple(BOSS_STATS)))
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
                self.drop_bio_pickup(zombie["x"], zombie["y"], random.choice(("damage", "rapid", "multishot", "shield", "speed", "ricochet", "cannon", "laser")))
        else:
            if random.random() < .18:
                self.drop_bio_pickup(zombie["x"], zombie["y"], "health")
            if random.random() < .035:
                self.drop_bio_pickup(zombie["x"], zombie["y"], random.choice(("damage", "rapid", "multishot", "shield", "speed", "ricochet", "cannon", "laser")))

    def move_zombie(self, zombie, dx, dy, dt, speed):
        radius = zombie["radius"]
        next_x = clamp(zombie["x"] + dx * speed * dt, radius, self.width - radius)
        if not any(circle_hits_rect(next_x, zombie["y"], radius, wall) for wall in self.active_terrain()):
            zombie["x"] = next_x
        next_y = clamp(zombie["y"] + dy * speed * dt, radius, self.height - radius)
        if not any(circle_hits_rect(zombie["x"], next_y, radius, wall) for wall in self.active_terrain()):
            zombie["y"] = next_y

    def zombie_volley(self, zombie, target, now, radial=False, count=1):
        base_angle = math.atan2(target["y"] - zombie["y"], target["x"] - zombie["x"])
        angles = [index * math.tau / count for index in range(count)] if radial else [base_angle]
        for angle in angles:
            self.add_bullet({"x": zombie["x"], "y": zombie["y"], "vx": math.cos(angle) * 460,
                             "vy": math.sin(angle) * 460, "owner": f"z{zombie['id']}", "color": "#9cff57",
                             "damage": zombie["damage"], "damage_type": "normal", "radius": 7,
                             "kind": "zombie", "bounces": 0, "life": 3.2, "created": now})

    def update_zombies(self, dt, now):
        if self.mode != "bio":
            return
        self.zombies = [zombie for zombie in self.zombies if zombie["hp"] > 0]
        if self.wave_active and not self.zombies:
            self.wave_active = False
            self.next_wave = now + 5
            for player in self.humans():
                if player["hp"] > 0:
                    player["hp"] = min(player["max_hp"], player["hp"] + player["max_hp"] * .2)
        if not self.wave_active and now >= self.next_wave and self.humans():
            self.start_bio_wave(now)
        if now >= self.next_bio_pickup:
            self.next_bio_pickup = now + random.uniform(22, 36)
            if random.random() < .35:
                x, y = self.random_open_position(45)
                self.drop_bio_pickup(x, y, random.choice(("damage", "rapid", "multishot", "shield", "speed", "ricochet", "cannon", "laser")))
        targets = [player for player in self.humans() if player["ready"] and player["hp"] > 0]
        if not targets:
            return
        for zombie in self.zombies:
            target = min(targets, key=lambda player: math.hypot(player["x"] - zombie["x"], player["y"] - zombie["y"]))
            dx, dy = target["x"] - zombie["x"], target["y"] - zombie["y"]
            distance = max(1, math.hypot(dx, dy))
            if now >= zombie["next_think"]:
                zombie["next_think"] = now + random.uniform(.18, .3)
                if zombie["kind"] == "shooter" and distance < 290:
                    move_x, move_y = self.bot_steering(zombie, zombie["x"] - dx, zombie["y"] - dy)
                elif zombie["kind"] == "shooter" and distance < 470:
                    move_x, move_y = -dy / distance, dx / distance
                else:
                    move_x, move_y = self.bot_steering(zombie, target["x"], target["y"])
                zombie["move_x"], zombie["move_y"] = move_x, move_y
            speed = zombie["speed"]
            if zombie["kind"] == "iron_abomination" and now < zombie["charge_until"]:
                speed *= 2.8
            self.move_zombie(zombie, zombie["move_x"], zombie["move_y"], dt, speed)
            if distance <= zombie["radius"] + PLAYER_RADIUS + 7 and now - zombie["last_attack"] >= .8:
                zombie["last_attack"] = now
                self.damage(target, zombie["damage"], "", now)
            if zombie["kind"] == "shooter" and distance < 720 and now - zombie["last_shot"] >= 1.35 and self.path_clear(zombie["x"], zombie["y"], target["x"], target["y"], 5):
                zombie["last_shot"] = now
                self.zombie_volley(zombie, target, now)
            if zombie.get("boss") and now >= zombie["next_special"]:
                if zombie["kind"] == "plague_lord":
                    zombie["next_special"] = now + 3.8
                    self.zombie_volley(zombie, target, now, radial=True, count=12)
                    for player in targets:
                        if math.hypot(player["x"] - zombie["x"], player["y"] - zombie["y"]) < 190:
                            self.damage(player, 6 + self.wave, "", now)
                elif zombie["kind"] == "brood_queen":
                    zombie["next_special"] = now + 6
                    for _ in range(3):
                        runner = self.spawn_zombie("runner", now)
                        runner["x"], runner["y"] = zombie["x"] + random.uniform(-55, 55), zombie["y"] + random.uniform(-55, 55)
                else:
                    zombie["next_special"] = now + 6.5
                    zombie["charge_until"] = now + 1.6
                    self.zombie_volley(zombie, target, now, radial=True, count=8)

    def add_bullet(self, bullet):
        bullet["id"] = self.next_bullet_id
        self.next_bullet_id += 1
        self.bullets.append(bullet)

    def spawn(self, player):
        x, y = self.random_open_position(PLAYER_RADIUS + 15)
        player.update(x=x, y=y, hp=player.get("max_hp", 100))

    @staticmethod
    def next_level_score(level):
        return level * (level + 1) // 2

    def next_level_xp(self, level):
        return math.ceil(4 * level ** 1.65) if self.mode == "bio" else self.next_level_score(level)

    def apply_upgrade(self, player, upgrade):
        if self.mode not in {"upgrade", "bio"} or upgrade not in UPGRADE_MAX_RANKS:
            return False
        ranks = player.setdefault("upgrades", {})
        if ranks.get(upgrade, 0) >= UPGRADE_MAX_RANKS[upgrade]:
            return False
        ranks[upgrade] = ranks.get(upgrade, 0) + 1
        if upgrade == "vitality":
            player["max_hp"] += 15
            player["hp"] = min(player["max_hp"], player["hp"] + 15)
        player["upgrade_choices"] = []
        self.check_level_up(player)
        return True

    def check_level_up(self, player):
        if self.mode not in {"upgrade", "bio"} or player.get("upgrade_choices"):
            return
        while player.get("level", 1) < 1 + sum(UPGRADE_MAX_RANKS.values()):
            if player.get("xp", player["score"]) < self.next_level_xp(player["level"]):
                return
            player["level"] += 1
            choices = [kind for kind, maximum in UPGRADE_MAX_RANKS.items()
                       if player.get("upgrades", {}).get(kind, 0) < maximum]
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
        player["max_hp"] = 300 if role == "tank" else 100
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
        if target["effects"].get("invincible", 0) > now:
            return
        if target["effects"].get("shield", 0) > now:
            amount *= 0.25 if damage_type == "laser" else 0.5
        target["hp"] -= amount
        if target["hp"] <= 0:
            target["hp"] = 0
            target["respawn"] = now + 2.5
            owner = self.players.get(owner_id)
            if owner:
                owner["score"] += 1
                if self.mode == "upgrade":
                    owner["xp"] = owner.get("xp", 0) + 1
                if owner.get("role") == "necromancer":
                    self.add_minion(owner, "roam")
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

    def apply_pickup(self, player, kind, now):
        if kind == "health":
            player["hp"] = min(player.get("max_hp", 100), player["hp"] + player.get("max_hp", 100) * 0.25)
        elif kind == "minion":
            self.add_minion(player)
        else:
            player["effects"][kind] = now + POWERUP_DURATION

    def explode_cannon(self, bullet, now):
        radius = 115
        self.explosions.append({"x": bullet["x"], "y": bullet["y"], "radius": radius,
                                "color": bullet["color"], "life": 0.35})
        if self.mode == "bio":
            for zombie in self.zombies:
                if zombie["hp"] > 0 and math.hypot(zombie["x"] - bullet["x"], zombie["y"] - bullet["y"]) < radius + zombie["radius"]:
                    self.damage_zombie(zombie, 70, bullet["owner"], now)
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
                enemies = ([zombie for zombie in self.zombies if zombie["hp"] > 0] if self.mode == "bio" else
                           [p for p in self.players.values() if p["id"] != owner["id"] and p["hp"] > 0])
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
            for target in self.players.values() if self.mode != "bio" else ():
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
        self.update_zombies(dt, now)
        for p in self.players.values():
            if not p["ready"]:
                continue
            if p["hp"] <= 0:
                if now >= p["respawn"]:
                    self.spawn(p)
                continue
            if not p.get("is_bot") and now - p.get("last_input", now) > 0.75:
                p["input"].update(up=False, down=False, left=False, right=False,
                                  move_x=0, move_y=0, shoot=False, ability=False)
            dx = p["input"].get("move_x", p["input"]["right"] - p["input"]["left"])
            dy = p["input"].get("move_y", p["input"]["down"] - p["input"]["up"])
            length = math.hypot(dx, dy)
            if length > 1:
                dx, dy = dx / length, dy / length
            upgrade_ranks = p.get("upgrades", {}) if self.mode in {"upgrade", "bio"} else {}
            speed = PLAYER_SPEED * (1.45 if p["effects"].get("speed", 0) > now else 1) * (1 + .06 * upgrade_ranks.get("agility", 0))
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
            if role == "paladin" and p["input"].get("ability"):
                self.activate_paladin(p, now)
            cooldown = 1.25 if cannon else 0.09 if beam else 0.55 if laser else 0.5 if role == "mage" else 0.7 if role == "sniper" else 0.11 if rapid else 0.24
            cooldown *= .9 ** upgrade_ranks.get("haste", 0)
            if p["input"]["shoot"] and now - p["last_shot"] >= cooldown:
                p["last_shot"] = now
                angle = p["input"]["angle"]
                if cannon:
                    self.add_bullet({"x": p["x"], "y": p["y"],
                                     "vx": math.cos(angle) * 430, "vy": math.sin(angle) * 430,
                                     "owner": p["id"], "color": p["color"], "damage": 70,
                                     "damage_type": "explosive", "radius": 18, "kind": "cannon",
                                     "bounces": 0, "life": 3, "created": now})
                elif laser:
                    self.fire_laser(p, angle, now, 50)
                elif beam:
                    self.fire_laser(p, angle, now, 8, beam=True)
                else:
                    arsenal_rank = upgrade_ranks.get("arsenal", 0)
                    angles = ((angle - 0.16, angle, angle + 0.16) if p["effects"].get("multishot", 0) > now else
                              (angle - .08, angle + .08) if arsenal_rank == 1 else
                              (angle - .13, angle, angle + .13) if arsenal_rank >= 2 else (angle,))
                    damage = (40 if p["effects"].get("damage", 0) > now else 25) * (1 + .1 * upgrade_ranks.get("power", 0))
                    if arsenal_rank:
                        damage *= .82 if arsenal_rank == 1 else .72
                    for shot_angle in angles:
                        bullet_kind = "mage" if role == "mage" else "sniper" if role == "sniper" else "bullet"
                        bullet_damage = 37.5 if role == "mage" else 75 if role == "sniper" else damage
                        bullet_speed = (1200 if role == "sniper" else 700 if role == "mage" else BULLET_SPEED) * (1 + .1 * upgrade_ranks.get("velocity", 0))
                        bullet_radius = 9 if role == "mage" else 5 if role == "sniper" else 6
                        self.add_bullet({"x": p["x"], "y": p["y"],
                                         "vx": math.cos(shot_angle) * bullet_speed,
                                         "vy": math.sin(shot_angle) * bullet_speed,
                                         "owner": p["id"], "color": p["color"], "damage": bullet_damage,
                                         "damage_type": "normal", "radius": bullet_radius, "kind": bullet_kind,
                                         "bounces": 3 if p["effects"].get("ricochet", 0) > now else 0,
                                         "life": 2.5, "created": now})

            for pickup in self.pickups:
                if pickup["active"] and math.hypot(p["x"] - pickup["x"], p["y"] - pickup["y"]) < 45:
                    self.apply_pickup(p, pickup["kind"], now)
                    pickup["active"] = False

        self.sync_pickups()
        self.update_minions(dt, now)

        alive = []
        for b in self.bullets:
            b["life"] -= dt
            if b["life"] <= 0:
                if b["kind"] == "cannon":
                    self.explode_cannon(b, now)
                continue
            previous_x, previous_y = b["x"], b["y"]
            hit = not self.advance_bullet(b, dt)
            if hit and b["kind"] == "cannon":
                self.explode_cannon(b, now)
            elif hit and b["kind"] == "mage":
                self.explode_magic(b, now)
            if not hit:
                if self.mode == "bio" and b["kind"] != "zombie":
                    zombie = next((zombie for zombie in self.zombies if zombie["hp"] > 0 and
                                   segment_hits_circle(previous_x, previous_y, b["x"], b["y"], zombie["x"], zombie["y"], zombie["radius"] + b["radius"])), None)
                    if zombie:
                        if b["kind"] == "cannon":
                            self.explode_cannon(b, now)
                        else:
                            self.damage_zombie(zombie, b["damage"], b["owner"], now)
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
                continue
            for p in self.players.values() if self.mode != "bio" or b["kind"] == "zombie" else ():
                player_hit = (segment_hits_circle(previous_x, previous_y, b["x"], b["y"], p["x"], p["y"], PLAYER_RADIUS + b["radius"])
                              if self.mode == "bio" else math.hypot(p["x"] - b["x"], p["y"] - b["y"]) < PLAYER_RADIUS + b["radius"])
                if p["id"] != b["owner"] and p["hp"] > 0 and player_hit:
                    if b["kind"] == "cannon":
                        self.explode_cannon(b, now)
                    elif b["kind"] == "mage":
                        self.explode_magic(b, now)
                    else:
                        self.damage(p, b["damage"], b["owner"], now, b["damage_type"])
                    hit = True
                    break
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
        payload = json.dumps({"type": "state", "server_time": round(now * 1000, 3), "players": [
            {**{k: p[k] for k in ("id", "name", "max_hp", "score", "color", "role", "ready")},
             "bot": p.get("is_bot", False),
             "bot_difficulty": "hard" if p.get("is_bot") else None,
             "level": p.get("level", 1), "xp": p.get("xp", p.get("score", 0)), "upgrades": p.get("upgrades", {}),
             "upgrade_choices": p.get("upgrade_choices", []),
             "next_level_score": self.next_level_xp(p.get("level", 1)) if p.get("level", 1) < 1 + sum(UPGRADE_MAX_RANKS.values()) else None,
             "x": round(p["x"], 1), "y": round(p["y"], 1), "hp": round(p["hp"], 1),
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
           "zombies": [{"id": zombie["id"], "kind": zombie["kind"], "boss": zombie["boss"],
                         "boss_name": zombie.get("boss_name"), "x": round(zombie["x"], 1), "y": round(zombie["y"], 1),
                         "hp": round(zombie["hp"], 1), "max_hp": zombie["max_hp"], "radius": zombie["radius"],
                         "move_x": round(zombie.get("move_x", 0), 3), "move_y": round(zombie.get("move_y", 0), 3)}
                        for zombie in self.zombies if zombie["hp"] > 0],
           "bio": {"wave": self.wave, "active": self.wave_active,
                   "remaining": sum(1 for zombie in self.zombies if zombie["hp"] > 0),
                   "next_wave": max(0, round(self.next_wave - now, 1)) if not self.wave_active else 0,
                   "boss": next((zombie.get("boss_name") for zombie in self.zombies if zombie.get("boss") and zombie["hp"] > 0), None)} if self.mode == "bio" else None,
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
                  "hp": 0, "max_hp": 100, "score": 0, "color": room.next_player_color(), "ws": ws, "is_bot": False, "last_shot": 0,
                  "respawn": 0, "effects": {}, "minions": [], "role": None, "ready": ready,
                  "next_weapon": 0, "ability_ready": 0, "master_weapon": None, "last_chat": 0,
                  "level": 1, "xp": 0, "upgrades": {}, "upgrade_choices": [],
                  "last_input": time.monotonic(), "input_seq": -1,
                  "input": {"up": 0, "down": 0, "left": 0, "right": 0, "shoot": False, "ability": False, "angle": 0}}
        if ready:
            room.spawn(player)
        room.players[pid] = player
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
                    for key in ("up", "down", "left", "right", "shoot", "ability"):
                        inp[key] = bool(data.get(key))
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
                elif data.get("type") == "ability":
                    room.activate_paladin(player, time.monotonic())
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
