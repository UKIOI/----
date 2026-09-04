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
