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
TICK_RATE = 30
NETWORK_RATE = 30
PROTOCOL_VERSION = 11
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
BOT_DIFFICULTIES = {
    "easy": {"reaction": 0.48, "aim_error": 0.24, "speed": 0.72, "fire_chance": 0.55, "preferred": 390},
    "normal": {"reaction": 0.24, "aim_error": 0.10, "speed": 0.88, "fire_chance": 0.82, "preferred": 340},
    "hard": {"reaction": 0.11, "aim_error": 0.035, "speed": 1.0, "fire_chance": 0.97, "preferred": 300},
}
BOT_ROLES = ("tank", "mage", "sniper", "necromancer", "weaponmaster", "paladin")
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

rooms: dict[str, "Room"] = {}


def clamp(value, low, high):
    return max(low, min(high, value))


def circle_hits_rect(x, y, radius, rect):
    closest_x = clamp(x, rect["x"], rect["x"] + rect["w"])
    closest_y = clamp(y, rect["y"], rect["y"] + rect["h"])
    return (x - closest_x) ** 2 + (y - closest_y) ** 2 < radius ** 2


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


def build_terrain():
    terrain, block_id = [], 0
    for obstacle in OBSTACLES:
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
        self.players = {}
        self.bullets = []
        self.lasers = []
        self.explosions = []
        self.pickups = []
        self.terrain = build_terrain()
        self.next_pickup_id = 0
        self.next_minion_id = 0
        self.bot_difficulty = "normal"
        self.last = time.monotonic()
        self.last_broadcast = 0
        self.task = asyncio.create_task(self.loop())

    def random_open_position(self, margin):
        for _ in range(200):
            x, y = random.randint(margin, WIDTH - margin), random.randint(margin, HEIGHT - margin)
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
        desired = len(self.players) * 3 if self.mode == "items" else 0 if self.mode == "pure" else len(self.players)
        if len(self.pickups) > desired:
            self.pickups = self.pickups[:desired]
        while len(self.pickups) < desired:
            x, y = self.random_open_position(45)
            kind = "health" if self.mode == "profession" else random.choice(POWERUP_TYPES)
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

    def configure_bots(self, count, difficulty):
        difficulty = difficulty if difficulty in BOT_DIFFICULTIES else "normal"
        self.bot_difficulty = difficulty
        removed_ids = {pid for pid, player in self.players.items() if player.get("is_bot")}
        for pid in removed_ids:
            self.players.pop(pid, None)
        self.bullets = [bullet for bullet in self.bullets if bullet["owner"] not in removed_ids]
        self.lasers = [laser for laser in self.lasers if laser["owner"] not in removed_ids]
        try:
            count = int(count)
        except (TypeError, ValueError, OverflowError):
            count = 0
        count = max(0, min(count, 12 - len(self.humans())))
        for index in range(count):
            pid = f"bot-{secrets.token_hex(4)}"
            ready = self.mode != "profession"
            bot = {"id": pid, "name": f"人机 {index + 1}", "x": 0, "y": 0,
                   "hp": 0, "max_hp": 100, "score": 0, "color": self.next_player_color(),
                   "ws": None, "is_bot": True, "difficulty": difficulty, "last_shot": 0,
                   "respawn": 0, "effects": {}, "minions": [], "role": None, "ready": ready,
                   "next_weapon": 0, "ability_ready": 0, "master_weapon": None, "last_chat": 0,
                   "bot_next_think": 0, "bot_strafe": random.choice((-1, 1)),
                   "input": {"up": False, "down": False, "left": False, "right": False,
                             "move_x": 0, "move_y": 0, "shoot": False, "ability": False, "angle": 0}}
            self.players[pid] = bot
            if ready:
                self.spawn(bot)
            else:
                self.select_role(bot, random.choice(BOT_ROLES))
        self.sync_pickups()

    def path_clear(self, start_x, start_y, end_x, end_y, radius=PLAYER_RADIUS + 2):
        distance = math.hypot(end_x - start_x, end_y - start_y)
        steps = max(1, math.ceil(distance / 20))
        terrain = list(self.active_terrain())
        for step in range(1, steps + 1):
            ratio = step / steps
            x = start_x + (end_x - start_x) * ratio
            y = start_y + (end_y - start_y) * ratio
            if any(circle_hits_rect(x, y, radius, obstacle) for obstacle in terrain):
                return False
        return True

    def navigation_direction(self, start_x, start_y, goal_x, goal_y):
        direct_x, direct_y = goal_x - start_x, goal_y - start_y
        direct_length = math.hypot(direct_x, direct_y)
        if direct_length < 4:
            return 0, 0
        if self.path_clear(start_x, start_y, goal_x, goal_y):
            return direct_x / direct_length, direct_y / direct_length

        columns, rows = math.ceil(WIDTH / NAV_CELL), math.ceil(HEIGHT / NAV_CELL)
        terrain = list(self.active_terrain())
        open_cache = {}

        def cell_center(cell):
            column, row = cell
            return min(WIDTH - PLAYER_RADIUS, column * NAV_CELL + NAV_CELL / 2), min(HEIGHT - PLAYER_RADIUS, row * NAV_CELL + NAV_CELL / 2)

        def walkable(cell):
            if cell in open_cache:
                return open_cache[cell]
            column, row = cell
            if not (0 <= column < columns and 0 <= row < rows):
                return False
            x, y = cell_center(cell)
            result = not any(circle_hits_rect(x, y, PLAYER_RADIUS + 3, obstacle) for obstacle in terrain)
            open_cache[cell] = result
            return result

        def nearest_open(x, y):
            origin = (int(clamp(x // NAV_CELL, 0, columns - 1)), int(clamp(y // NAV_CELL, 0, rows - 1)))
            if walkable(origin):
                return origin
            for radius in range(1, 6):
                candidates = []
                for offset_x in range(-radius, radius + 1):
                    for offset_y in (-radius, radius):
                        candidates.append((origin[0] + offset_x, origin[1] + offset_y))
                for offset_y in range(-radius + 1, radius):
                    for offset_x in (-radius, radius):
                        candidates.append((origin[0] + offset_x, origin[1] + offset_y))
                valid = [cell for cell in candidates if walkable(cell)]
                if valid:
                    return min(valid, key=lambda cell: math.hypot(cell_center(cell)[0] - x, cell_center(cell)[1] - y))
            return None

        start, goal = nearest_open(start_x, start_y), nearest_open(goal_x, goal_y)
        if start is None or goal is None:
            return direct_x / direct_length, direct_y / direct_length
        frontier = [(0, start)]
        came_from, cost = {start: None}, {start: 0}
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
            return direct_x / direct_length, direct_y / direct_length
        path, current = [], goal
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse()
        waypoint_x, waypoint_y = cell_center(path[min(1, len(path) - 1)])
        for cell in path[2:7]:
            candidate_x, candidate_y = cell_center(cell)
            if not self.path_clear(start_x, start_y, candidate_x, candidate_y):
                break
            waypoint_x, waypoint_y = candidate_x, candidate_y
        move_x, move_y = waypoint_x - start_x, waypoint_y - start_y
        move_length = math.hypot(move_x, move_y) or 1
        return move_x / move_length, move_y / move_length

    def safest_position(self, bot, enemies):
        best = (bot["x"], bot["y"])
        best_score = -math.inf
        for distance in (280, 480, 680):
            for index in range(16):
                angle = index * math.tau / 16
                x = clamp(bot["x"] + math.cos(angle) * distance, PLAYER_RADIUS, WIDTH - PLAYER_RADIUS)
                y = clamp(bot["y"] + math.sin(angle) * distance, PLAYER_RADIUS, HEIGHT - PLAYER_RADIUS)
                if any(circle_hits_rect(x, y, PLAYER_RADIUS + 3, obstacle) for obstacle in self.active_terrain()):
                    continue
                enemy_distance = min(math.hypot(enemy["x"] - x, enemy["y"] - y) for enemy in enemies)
                travel = math.hypot(x - bot["x"], y - bot["y"])
                score = enemy_distance - travel * 0.12
                if score > best_score:
                    best, best_score = (x, y), score
        return best

    def dodge_direction(self, bot):
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
            if not 0 < along < speed * 0.55:
                continue
            closest_x = bullet["x"] + velocity_x * along
            closest_y = bullet["y"] + velocity_y * along
            miss_x, miss_y = bot["x"] - closest_x, bot["y"] - closest_y
            miss = math.hypot(miss_x, miss_y)
            if miss >= PLAYER_RADIUS + bullet.get("radius", 6) + 28:
                continue
            side = 1 if velocity_x * relative_y - velocity_y * relative_x >= 0 else -1
            urgency = 1 - along / (speed * 0.55)
            dodge_x += -velocity_y * side * (0.6 + urgency)
            dodge_y += velocity_x * side * (0.6 + urgency)
        length = math.hypot(dodge_x, dodge_y)
        return (dodge_x / length, dodge_y / length) if length else None

    def update_bots(self, now):
        for bot in self.bots():
            if self.mode == "profession" and not bot["ready"]:
                if now >= bot.get("respawn", 0):
                    self.select_role(bot, random.choice(BOT_ROLES), now)
                else:
                    continue
            if not bot["ready"] or bot["hp"] <= 0 or now < bot.get("bot_next_think", 0):
                continue
            settings = BOT_DIFFICULTIES[bot.get("difficulty", self.bot_difficulty)]
            bot["bot_next_think"] = now + settings["reaction"] * random.uniform(0.82, 1.18)
            enemies = [player for player in self.players.values()
                       if player["id"] != bot["id"] and player["ready"] and player["hp"] > 0]
            if not enemies:
                bot["input"].update(move_x=0, move_y=0, shoot=False, ability=False)
                continue
            target = min(enemies, key=lambda player: math.hypot(player["x"] - bot["x"], player["y"] - bot["y"]))
            dx, dy = target["x"] - bot["x"], target["y"] - bot["y"]
            distance = max(1, math.hypot(dx, dy))
            toward_x, toward_y = dx / distance, dy / distance
            low_health = bot["hp"] <= bot.get("max_hp", 100) * 0.35
            health_pickups = [pickup for pickup in self.pickups if pickup["active"] and pickup["kind"] == "health"]
            pickup_range = {"easy": 430, "normal": 650, "hard": 900}[bot.get("difficulty", self.bot_difficulty)]
            useful_pickups = [pickup for pickup in self.pickups if pickup["active"] and
                              math.hypot(pickup["x"] - bot["x"], pickup["y"] - bot["y"]) <= pickup_range]
            dodge = self.dodge_direction(bot)
            if dodge:
                move_x, move_y = dodge
                bot["bot_goal_kind"] = "dodge"
            elif low_health and distance < 360:
                safe_x, safe_y = self.safest_position(bot, enemies)
                move_x, move_y = self.navigation_direction(bot["x"], bot["y"], safe_x, safe_y)
                bot["bot_goal_kind"] = "retreat"
            elif low_health and health_pickups:
                pickup = min(health_pickups, key=lambda item: math.hypot(item["x"] - bot["x"], item["y"] - bot["y"]))
                move_x, move_y = self.navigation_direction(bot["x"], bot["y"], pickup["x"], pickup["y"])
                bot["bot_goal_kind"] = "health"
            elif low_health:
                safe_x, safe_y = self.safest_position(bot, enemies)
                move_x, move_y = self.navigation_direction(bot["x"], bot["y"], safe_x, safe_y)
                bot["bot_goal_kind"] = "retreat"
            elif useful_pickups:
                pickup_values = {"health": 5 if bot["hp"] < bot.get("max_hp", 100) else 0,
                                 "shield": 4, "speed": 3.5, "cannon": 3.2, "laser": 3.2,
                                 "beam": 3, "damage": 2.8, "rapid": 2.7, "multishot": 2.7,
                                 "ricochet": 2.4, "minion": 3.4}
                pickup = max(useful_pickups, key=lambda item: pickup_values.get(item["kind"], 2) * 180 -
                             math.hypot(item["x"] - bot["x"], item["y"] - bot["y"]))
                move_x, move_y = self.navigation_direction(bot["x"], bot["y"], pickup["x"], pickup["y"])
                bot["bot_goal_kind"] = "pickup"
            elif distance > settings["preferred"] + 70:
                move_x, move_y = self.navigation_direction(bot["x"], bot["y"], target["x"], target["y"])
                bot["bot_goal_kind"] = "chase"
            elif distance < settings["preferred"] - 80:
                retreat_x = clamp(bot["x"] - toward_x * 260, PLAYER_RADIUS, WIDTH - PLAYER_RADIUS)
                retreat_y = clamp(bot["y"] - toward_y * 260, PLAYER_RADIUS, HEIGHT - PLAYER_RADIUS)
                move_x, move_y = self.navigation_direction(bot["x"], bot["y"], retreat_x, retreat_y)
                bot["bot_goal_kind"] = "space"
            else:
                strafe_x = clamp(bot["x"] - toward_y * bot["bot_strafe"] * 220, PLAYER_RADIUS, WIDTH - PLAYER_RADIUS)
                strafe_y = clamp(bot["y"] + toward_x * bot["bot_strafe"] * 220, PLAYER_RADIUS, HEIGHT - PLAYER_RADIUS)
                move_x, move_y = self.navigation_direction(bot["x"], bot["y"], strafe_x, strafe_y)
                bot["bot_goal_kind"] = "strafe"
                if random.random() < 0.16:
                    bot["bot_strafe"] *= -1
            move_length = math.hypot(move_x, move_y)
            if move_length > 1:
                move_x, move_y = move_x / move_length, move_y / move_length
            aim = math.atan2(dy, dx) + random.uniform(-settings["aim_error"], settings["aim_error"])
            bot["input"].update(move_x=move_x, move_y=move_y, angle=aim,
                                shoot=distance < 720 and (not low_health or random.random() < 0.45) and random.random() < settings["fire_chance"],
                                ability=bot.get("role") == "paladin" and distance < 520 and bot["hp"] < 75)

    def spawn(self, player):
        x, y = self.random_open_position(PLAYER_RADIUS + 15)
        player.update(x=x, y=y, hp=player.get("max_hp", 100))

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
        player["effects"]["invincible"] = now + 5
        player["effects"]["speed"] = max(player["effects"].get("speed", 0), now + 5)
        player["ability_ready"] = now + 20
        return True

    def move_player(self, player, dx, dy):
        next_x = clamp(player["x"] + dx, PLAYER_RADIUS, WIDTH - PLAYER_RADIUS)
        if not any(circle_hits_rect(next_x, player["y"], PLAYER_RADIUS, obstacle) for obstacle in self.active_terrain()):
            player["x"] = next_x
        next_y = clamp(player["y"] + dy, PLAYER_RADIUS, HEIGHT - PLAYER_RADIUS)
        if not any(circle_hits_rect(player["x"], next_y, PLAYER_RADIUS, obstacle) for obstacle in self.active_terrain()):
            player["y"] = next_y

    def settle_player_stop(self, player, target_x, target_y):
        distance = math.hypot(target_x - player["x"], target_y - player["y"])
        if not math.isfinite(distance) or distance > 70:
            return
        steps = max(1, math.ceil(distance / 5))
        for index in range(steps):
            remaining = steps - index
            self.move_player(player, (target_x - player["x"]) / remaining,
                             (target_y - player["y"]) / remaining)

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
                if owner.get("role") == "necromancer":
                    self.add_minion(owner, "roam")
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
                enemies = [p for p in self.players.values() if p["id"] != owner["id"] and p["hp"] > 0]
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
                self.bullets.append({"x": minion["x"], "y": minion["y"], "vx": math.cos(angle) * 620,
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
            candidates.append(((WIDTH - radius - old_x) / dx, (-1, 0)))
        elif dx < 0:
            candidates.append(((radius - old_x) / dx, (1, 0)))
        if dy > 0:
            candidates.append(((HEIGHT - radius - old_y) / dy, (0, -1)))
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
        bullet["x"] = clamp(bullet["x"] + bullet["vx"] / speed * (remaining + 0.1), radius, WIDTH - radius)
        bullet["y"] = clamp(bullet["y"] + bullet["vy"] / speed * (remaining + 0.1), radius, HEIGHT - radius)
        return True

    def fire_laser(self, player, angle, now, damage, beam=False):
        dx, dy = math.cos(angle), math.sin(angle)
        start_x, start_y, damaged = player["x"], player["y"], set()
        for segment in range(4):  # 初始光束 + 最多三次反射
            candidates = []
            if dx > 0:
                candidates.append(((WIDTH - start_x) / dx, (-1, 0)))
            elif dx < 0:
                candidates.append(((0 - start_x) / dx, (1, 0)))
            if dy > 0:
                candidates.append(((HEIGHT - start_y) / dy, (0, -1)))
            elif dy < 0:
                candidates.append(((0 - start_y) / dy, (0, 1)))
            for obstacle in self.active_terrain():
                hit = ray_rect_hit(start_x, start_y, dx, dy, obstacle)
                if hit:
                    candidates.append(hit)
            distance, normal = min((hit for hit in candidates if hit[0] > 0.01), key=lambda hit: hit[0])
            end_x, end_y = start_x + dx * distance, start_y + dy * distance
            for target in self.players.values():
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
        for p in self.players.values():
            if not p["ready"]:
                continue
            if p["hp"] <= 0:
                if now >= p["respawn"]:
                    self.spawn(p)
                continue
            dx = p["input"].get("move_x", p["input"]["right"] - p["input"]["left"])
            dy = p["input"].get("move_y", p["input"]["down"] - p["input"]["up"])
            length = math.hypot(dx, dy) or 1
            speed = PLAYER_SPEED * (1.45 if p["effects"].get("speed", 0) > now else 1)
            if p.get("is_bot"):
                speed *= BOT_DIFFICULTIES[p.get("difficulty", self.bot_difficulty)]["speed"]
            self.move_player(p, dx / length * speed * dt, dy / length * speed * dt)
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
            if p["input"]["shoot"] and now - p["last_shot"] >= cooldown:
                p["last_shot"] = now
                angle = p["input"]["angle"]
                if cannon:
                    self.bullets.append({"x": p["x"], "y": p["y"],
                                         "vx": math.cos(angle) * 430, "vy": math.sin(angle) * 430,
                                         "owner": p["id"], "color": p["color"], "damage": 70,
                                         "damage_type": "explosive", "radius": 18, "kind": "cannon",
                                         "bounces": 0, "life": 3, "created": now})
                elif laser:
                    self.fire_laser(p, angle, now, 50)
                elif beam:
                    self.fire_laser(p, angle, now, 8, beam=True)
                else:
                    angles = (angle - 0.16, angle, angle + 0.16) if p["effects"].get("multishot", 0) > now else (angle,)
                    damage = 40 if p["effects"].get("damage", 0) > now else 25
                    for shot_angle in angles:
                        bullet_kind = "mage" if role == "mage" else "sniper" if role == "sniper" else "bullet"
                        bullet_damage = 37.5 if role == "mage" else 75 if role == "sniper" else damage
                        bullet_speed = 1200 if role == "sniper" else 700 if role == "mage" else BULLET_SPEED
                        bullet_radius = 9 if role == "mage" else 5 if role == "sniper" else 6
                        self.bullets.append({"x": p["x"], "y": p["y"],
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
            hit = not self.advance_bullet(b, dt)
            if hit and b["kind"] == "cannon":
                self.explode_cannon(b, now)
            elif hit and b["kind"] == "mage":
                self.explode_magic(b, now)
            if not hit:
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
            for p in self.players.values():
                if p["id"] != b["owner"] and p["hp"] > 0 and math.hypot(p["x"] - b["x"], p["y"] - b["y"]) < PLAYER_RADIUS + b["radius"]:
                    if b["kind"] == "cannon":
                        self.explode_cannon(b, now)
                    elif b["kind"] == "mage":
                        self.explode_magic(b, now)
                    else:
                        self.damage(p, b["damage"], b["owner"], now, b["damage_type"])
                    hit = True
                    break
            if not hit and b["life"] > 0 and 0 < b["x"] < WIDTH and 0 < b["y"] < HEIGHT:
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
        payload = json.dumps({"type": "state", "players": [
            {**{k: p[k] for k in ("id", "name", "max_hp", "score", "color", "role", "ready")},
             "bot": p.get("is_bot", False),
             "x": round(p["x"], 1), "y": round(p["y"], 1), "hp": round(p["hp"], 1),
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
                          **{k: b[k] for k in ("owner", "color", "bounces", "radius", "kind")}} for b in self.bullets],
           "lasers": [{**{k: round(value, 1) if k in {"x1", "y1", "x2", "y2", "life"} else value
                           for k, value in laser.items() if k != "created"},
                       "age": round(max(0, now - laser.get("created", now)), 3)} for laser in self.lasers],
           "explosions": [{k: round(value, 1) if k in {"x", "y", "radius", "life"} else value
                            for k, value in explosion.items()} for explosion in self.explosions],
           "pickups": [p for p in self.pickups if p["active"]],
           "bot_count": len(self.bots()), "bot_difficulty": self.bot_difficulty,
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
                   "color": player["color"], "message": message}
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
        if mode not in {"classic", "items", "pure", "profession"}:
            mode = "classic"
        if code in rooms:
            room = rooms[code]
            if room.mode != mode:
                await ws.send_json({"type": "error", "message": "该房间已经使用其他玩法模式，请选择相同模式或更换房间号"})
                return ws
        else:
            room = Room(code, mode)
            rooms[code] = room
        if len(room.players) >= 12 and room.bots():
            room.players.pop(room.bots()[-1]["id"], None)
        if len(room.players) >= 12:
            await ws.send_json({"type": "error", "message": "房间已满（最多 12 人）"})
            return ws
        pid = secrets.token_hex(4)
        ready = mode != "profession"
        player = {"id": pid, "name": str(first.get("name", "玩家"))[:12] or "玩家", "x": 0, "y": 0,
                  "hp": 0, "max_hp": 100, "score": 0, "color": room.next_player_color(), "ws": ws,
                  "is_bot": False, "last_shot": 0,
                  "respawn": 0, "effects": {}, "minions": [], "role": None, "ready": ready,
                  "next_weapon": 0, "ability_ready": 0, "master_weapon": None, "last_chat": 0,
                  "input": {"up": 0, "down": 0, "left": 0, "right": 0, "shoot": False, "ability": False, "angle": 0}}
        if ready:
            room.spawn(player)
        room.players[pid] = player
        now = time.monotonic()
        await ws.send_json({"type": "welcome", "protocol": PROTOCOL_VERSION, "edition": "offline", "network_rate": NETWORK_RATE,
                            "id": pid, "room": code, "mode": mode, "width": WIDTH, "height": HEIGHT,
                            "obstacles": [{**{k: block[k] for k in ("id", "x", "y", "w", "h", "active")},
                                           "restore": max(0, round(block["restore"] - now, 1))}
                                          for block in room.terrain]})
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("type") == "input":
                    inp = player["input"]
                    was_moving = math.hypot(inp.get("move_x", 0), inp.get("move_y", 0)) > 0.01
                    for key in ("up", "down", "left", "right", "shoot", "ability"):
                        inp[key] = bool(data.get(key))
                    move_x = float(data.get("move_x", inp["right"] - inp["left"]))
                    move_y = float(data.get("move_y", inp["down"] - inp["up"]))
                    move_length = math.hypot(move_x, move_y)
                    if not math.isfinite(move_length):
                        move_x = move_y = 0
                    elif move_length > 1:
                        move_x, move_y = move_x / move_length, move_y / move_length
                    angle = float(data.get("angle", 0))
                    inp["move_x"], inp["move_y"] = move_x, move_y
                    inp["angle"] = angle if math.isfinite(angle) else 0
                    if was_moving and move_length <= 0.01:
                        room.settle_player_stop(player, float(data.get("stop_x", player["x"])),
                                                float(data.get("stop_y", player["y"])))
                elif data.get("type") == "select_role":
                    room.select_role(player, str(data.get("role", "")), time.monotonic())
                elif data.get("type") == "ability":
                    room.activate_paladin(player, time.monotonic())
                elif data.get("type") == "configure_bots":
                    room.configure_bots(data.get("count", 0), str(data.get("difficulty", "normal")))
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
            if not room.humans():
                rooms.pop(room.code, None)
                room.task.cancel()
    return ws


async def index(_):
    return web.FileResponse(ROOT / "public" / "index.html")


async def health(_):
    return web.json_response({"game": "neon-brawl", "edition": "offline", "status": "ok", "protocol": PROTOCOL_VERSION})


app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/health", health)
app.router.add_get("/ws", websocket)
app.router.add_static("/static", ROOT / "public")

if __name__ == "__main__":
    web.run_app(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8080)))
