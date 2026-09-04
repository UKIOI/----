import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.setdefault('APP_EDITION', 'local')
from app.game.engine import Room, finite_number, ray_rect_hit


def test_safe_numbers_and_laser_hit():
    assert finite_number('bad', 3) == 3
    assert ray_rect_hit(0, 50, 1, 0, {'x': 100, 'y': 0, 'w': 20, 'h': 100}) == (100, (-1, 0))


def test_room_starts_and_cancels():
    async def run():
        room = Room('TEST')
        assert room.mode == 'classic'
        room.task.cancel()
    asyncio.run(run())


def test_room_configures_offline_bots():
    async def run():
        room = Room('BOTS')
        try:
            human = {"id": "human", "name": "玩家", "x": 0, "y": 0,
                     "hp": 0, "max_hp": 100, "score": 0, "color": "#fff", "ws": None,
                     "is_bot": False, "last_shot": 0, "respawn": 0, "effects": {},
                     "minions": [], "role": None, "ready": True, "next_weapon": 0,
                     "ability_ready": 0, "master_weapon": None, "last_chat": 0,
                     "last_input": 0, "input_seq": -1,
                     "input": {"up": 0, "down": 0, "left": 0, "right": 0,
                               "shoot": False, "ability": False, "angle": 0}}
            room.players[human["id"]] = human
            room.spawn(human)
            room.configure_bots(3, "hard")
            assert len(room.humans()) == 1
            assert len(room.bots()) == 3
            assert room.bot_difficulty == "hard"
            assert all(bot["ready"] and bot["hp"] > 0 for bot in room.bots())
            room.configure_bots(99, "bad")
            assert len(room.bots()) == 11
            assert room.bot_difficulty == "normal"
        finally:
            room.task.cancel()
    asyncio.run(run())
