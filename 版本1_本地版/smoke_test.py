import asyncio
import json
import os
import time
import uuid

import aiohttp

from server import COLORS, Room, ray_rect_hit


async def main():
    run_id = uuid.uuid4().hex[:8].upper()
    color_room = Room("COLORS")
    assigned_colors = []
    for index in range(12):
        color = color_room.next_player_color()
        assigned_colors.append(color)
        color_room.players[str(index)] = {"color": color}
    assert len(COLORS) >= 12 and len(set(assigned_colors)) == 12, "满房玩家颜色没有保持唯一"
    color_room.task.cancel()
    hit = ray_rect_hit(0, 50, 1, 0, {"x": 100, "y": 0, "w": 20, "h": 100})
    assert hit == (100, (-1, 0)), "激光墙面法线计算错误"
    unit_room = Room("UNIT")
    shooter = {"id": "shooter", "x": 100, "y": 100, "color": "#abcdef", "hp": 100, "score": 0, "effects": {}}
    target = {"id": "target", "x": 200, "y": 100, "hp": 100, "effects": {}, "respawn": 0}
    unit_room.players = {"shooter": shooter, "target": target}
    unit_room.fire_laser(shooter, 0, time.monotonic(), 50)
    assert len(unit_room.lasers) == 4 and unit_room.lasers[0]["owner"] == "shooter" and unit_room.lasers[0]["segment"] == 0, "激光没有形成初始段和三次反射段或缺少发射者信息"
    assert target["hp"] == 50, "普通激光没有造成一击半血伤害"
    target["hp"], unit_room.lasers = 100, []
    unit_room.fire_laser(shooter, 0, time.monotonic(), 8, beam=True)
    assert target["hp"] == 92 and len(unit_room.lasers) == 4, "高能光束伤害或反射错误"
    shielded = {"id": "shielded", "hp": 100, "effects": {"shield": time.monotonic() + 5}, "respawn": 0}
    unit_room.damage(shielded, 25, "shooter", time.monotonic())
    assert shielded["hp"] == 87.5, "护盾普通伤害减免错误"
    unit_room.damage(shielded, 50, "shooter", time.monotonic(), "laser")
    assert shielded["hp"] == 75, "护盾激光伤害减免错误"
    wounded = {"id": "wounded", "hp": 60, "effects": {}}
    unit_room.apply_pickup(wounded, "health", time.monotonic())
    assert wounded["hp"] == 85, "血包治疗量错误"
    unit_room.apply_pickup(wounded, "health", time.monotonic())
    assert wounded["hp"] == 100, "血包治疗超过生命上限"
    ricochet = {"x": 10, "y": 100, "vx": -100, "vy": 0, "bounces": 3}
    assert unit_room.advance_bullet(ricochet, 0.1) and ricochet["vx"] == 100 and ricochet["bounces"] == 2, "子弹边界反弹错误"
    follower_owner = {"id": "owner", "x": 500, "y": 500, "hp": 100, "color": "#55d6be", "effects": {}, "minions": []}
    unit_room.apply_pickup(follower_owner, "minion", time.monotonic())
    unit_room.apply_pickup(follower_owner, "minion", time.monotonic())
    assert len(follower_owner["minions"]) == 2 and follower_owner["minions"][0]["hp"] == 100 / 3, "随从叠加或血量错误"
    enemy = {"id": "enemy", "x": 600, "y": 500, "hp": 100, "effects": {}, "minions": []}
    unit_room.players = {"owner": follower_owner, "enemy": enemy}
    unit_room.update_minions(0.1, time.monotonic())
    assert any(bullet["kind"] == "minion" and bullet["damage"] == 10 and bullet["life"] == 2.2 for bullet in unit_room.bullets), "随从射击或射程错误"
    unit_room.players = {"shooter": shooter, "target": target}
    cannonball = {"x": 270, "y": 170, "owner": "shooter", "color": "#abcdef"}
    unit_room.explode_cannon(cannonball, time.monotonic())
    destroyed = [block for block in unit_room.terrain if not block["active"]]
    assert destroyed and all(block["restore"] > time.monotonic() + 4.8 for block in destroyed), "大炮没有摧毁地形或设置恢复时间"
    for block in destroyed:
        block["restore"] = time.monotonic() - 1
    unit_room.restore_terrain(time.monotonic())
    assert all(block["active"] for block in destroyed), "地形没有在倒计时结束后恢复"
    wall_bounce = {"x": 240, "y": 170, "vx": 100, "vy": 0, "bounces": 3}
    assert unit_room.advance_bullet(wall_bounce, 0.2) and wall_bounce["vx"] == -100, "子弹障碍物反弹错误"
    wall_shot = {"x": 225, "y": 170, "vx": 760, "vy": 0, "radius": 6, "bounces": 0}
    assert not unit_room.advance_bullet(wall_shot, 0.1), "贴墙射击穿过了障碍物"
    unit_room.task.cancel()

    class_room = Room("CLASS_UNIT", "profession")
    class_player = {"id": "class", "name": "职业", "x": 100, "y": 100, "hp": 100, "max_hp": 100,
                    "score": 0, "color": "#64a8ff", "last_shot": 0, "respawn": 0, "effects": {},
                    "minions": [], "role": "mage", "ready": True,
                    "input": {"up": False, "down": False, "left": False, "right": False, "shoot": True, "angle": 0}}
    class_room.players = {"class": class_player}
    class_room.update(0.01, time.monotonic())
    assert class_room.bullets[0]["kind"] == "mage" and class_room.bullets[0]["damage"] == 37.5 and class_room.bullets[0]["life"] > 2.4, "法师爆炸弹属性或射程错误"
    class_room.bullets.clear()
    class_player.update(role="sniper", last_shot=0)
    class_room.update(0.01, time.monotonic())
    assert class_room.bullets[0]["kind"] == "sniper" and class_room.bullets[0]["damage"] == 75 and class_room.bullets[0]["vx"] == 1200, "狙击手三倍伤害或弹速错误"
    necromancer = {**class_player, "id": "necro", "role": "necromancer", "score": 0, "minions": []}
    victim = {"id": "victim", "hp": 100, "max_hp": 100, "score": 4, "effects": {"speed": time.monotonic() + 5},
              "minions": [{"id": 99}], "respawn": 0, "role": "sniper", "ready": True}
    class_room.players = {"necro": necromancer, "victim": victim}
    death_time = time.monotonic()
    class_room.damage(victim, 100, "necro", death_time)
    assert len(necromancer["minions"]) == 1 and necromancer["minions"][0]["movement"] == "roam", "死灵法师击杀没有转化自主随从"
    assert not victim["ready"] and victim["role"] is None and not victim["effects"] and not victim["minions"], "职业玩家死亡后没有重置并等待选角"
    class_room.select_role(victim, "tank", death_time + 0.1)
    assert victim["ready"] and victim["role"] == "tank" and victim["hp"] == 300 and victim["score"] == 4, "死亡后重新选角或分数保留错误"
    now = time.monotonic()
    weaponmaster = {**class_player, "id": "master", "role": "weaponmaster", "effects": {}, "minions": [],
                    "input": {**class_player["input"], "shoot": False, "ability": False},
                    "next_weapon": now - 1, "master_weapon": None}
    class_room.players = {"master": weaponmaster}
    class_room.update(0.01, now)
    assert weaponmaster["master_weapon"] in {"multishot", "laser", "beam", "ricochet", "cannon"}, "武器大师没有获得随机武器"
    assert weaponmaster["effects"][weaponmaster["master_weapon"]] == now + 10 and weaponmaster["next_weapon"] == now + 20, "武器大师持续时间或周期错误"
    paladin = {**class_player, "id": "paladin", "role": "paladin", "effects": {}, "ability_ready": 0}
    assert class_room.activate_paladin(paladin, now), "圣骑士技能无法发动"
    class_room.damage(paladin, 999, "enemy", now)
    assert paladin["hp"] == 100 and paladin["effects"]["invincible"] == now + 5 and paladin["effects"]["speed"] == now + 5 and paladin["ability_ready"] == now + 20, "圣骑士无敌、加速或冷却错误"
    class_room.task.cancel()
    base_url = f"http://127.0.0.1:{os.environ.get('TEST_PORT', '8080')}"
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/") as response:
            assert response.status == 200
            page = await response.text()
            assert "霓虹乱斗" in page and 'viewport-fit=cover' in page and 'id="rotateNotice"' in page, "横屏安全区界面未加载"
            assert 'data-role="weaponmaster"' in page and 'data-role="paladin"' in page and 'id="skillButton"' in page, "新职业界面未加载"
            assert 'id="joystick"' in page and 'id="aimJoystick"' in page, "手机双轮盘界面未加载"
            assert 'id="chatToggle"' in page and 'id="chatPanel"' in page and 'id="chatForm"' in page, "折叠聊天界面未加载"
        async with session.get(f"{base_url}/static/game.js?v=26") as response:
            mobile_script = await response.text()
            assert "visualViewport" in mobile_script and "viewWidth" in mobile_script and "orientationchange" in mobile_script, "动态横屏适配脚本未加载"
            assert "viewScale" in mobile_script and "smoothPositions" in mobile_script and "function visible" in mobile_script, "移动端视野或性能优化未加载"
            assert "touchMove" in mobile_script and "touchAim" in mobile_script and 'aimJoystick.addEventListener("pointerdown"' in mobile_script, "双轮盘输入脚本未加载"
            assert "KEY_CODES" in mobile_script and "sendInput(performance.now(), true)" in mobile_script, "键盘兼容输入脚本未加载"
            assert "appendChatMessage" in mobile_script and "message.textContent" in mobile_script and "stopGameInput" in mobile_script, "安全聊天或输入隔离脚本未加载"
            assert "new Map(data.destroyed" in mobile_script, "增量地形同步脚本未加载"
            assert "updateLocalPrediction" in mobile_script and "reconcilePrediction" in mobile_script and "updateLatency" in mobile_script, "本机移动预测或延迟检测脚本未加载"
            assert "beginPredictionHold" in mobile_script and "predictionHoldUntil" in mobile_script, "停止移动防抖校正脚本未加载"
            assert "stateReceivedAt" in mobile_script and "bulletX" in mobile_script and "drawProjectiles(now)" in mobile_script, "子弹帧间预测脚本未加载"
            assert "extrapolatedBulletPosition" in mobile_script, "子弹预测缺少墙体碰撞限制"
            assert all(marker in mobile_script for marker in ("visualBullet", "aimOrigin", "move_x", "baseLead", "serverMoving", "ws.bufferedAmount")), "移动、停止确认、瞄准或枪口显示优化未加载"

        first = await session.ws_connect(f"{base_url}/ws")
        second = await session.ws_connect(f"{base_url}/ws")
        await first.send_json({"name": "A", "room": run_id})
        await second.send_json({"name": "B", "room": run_id})
        first_welcome = json.loads((await first.receive()).data)
        second_welcome = json.loads((await second.receive()).data)
        assert first_welcome["room"] == run_id and second_welcome["room"] == run_id
        assert first_welcome["protocol"] == 9 and first_welcome["edition"] == "local" and len(first_welcome["obstacles"]) > 8, "初始地形或压缩协议未发送"
        for _ in range(10):
            state = json.loads((await first.receive()).data)
            if state.get("type") == "state" and len(state["players"]) == 2:
                break
        else:
            raise AssertionError("两个客户端未收到同一房间的状态")
        assert len(state["pickups"]) == len(state["players"]) == 2, "道具数量没有跟随在线人数"
        assert all(pickup["kind"] in {"damage", "rapid", "multishot", "laser", "shield", "speed", "beam", "health", "ricochet", "cannon", "minion"}
                   for pickup in state["pickups"]), "出现未知道具"
        assert "obstacles" not in state and state.get("destroyed") == [], "状态帧仍在重复发送完整地形"
        assert "lasers" in state, "激光状态未同步"
        await first.send_json({"type": "ping", "sent": 123.5})
        for _ in range(20):
            pong = json.loads((await first.receive()).data)
            if pong.get("type") == "pong":
                break
        else:
            raise AssertionError("延迟检测没有收到响应")
        assert pong["sent"] == 123.5, "延迟检测时间戳错误"
        await first.send_json({"type": "chat", "message": "  大家   好  "})
        for _ in range(20):
            chat = json.loads((await second.receive()).data)
            if chat.get("type") == "chat":
                break
        else:
            raise AssertionError("房间聊天消息未同步")
        assert chat["name"] == "A" and chat["message"] == "大家 好" and chat["color"], "聊天内容清理或玩家信息错误"
        before = next(p["x"] for p in state["players"] if p["name"] == "A")
        await first.send_json({"type": "input", "right": True, "move_x": 0.5, "move_y": 0, "angle": 0})
        moved = False
        for _ in range(20):
            state = json.loads((await first.receive()).data)
            player = next((p for p in state.get("players", []) if p["name"] == "A"), None)
            if player and player["x"] > before:
                moved = True
                break
        assert moved, "服务端没有处理移动输入"
        await first.send_json({"type": "input", "move_x": 0, "move_y": 0, "angle": 0})
        for _ in range(10):
            stopped_state = json.loads((await first.receive()).data)
            stopped_player = next((p for p in stopped_state.get("players", []) if p["name"] == "A"), None)
            if stopped_player and stopped_player["move_x"] == stopped_player["move_y"] == 0:
                break
        else:
            raise AssertionError("服务器没有确认停止移动")
        player_color = player["color"]
        owned_bullet = None
        for angle in (0, 1.57, 3.14, -1.57):
            await first.send_json({"type": "input", "shoot": True, "angle": angle})
            for _ in range(8):
                state = json.loads((await first.receive()).data)
                owned_bullet = next((bullet for bullet in state.get("bullets", []) if bullet["color"] == player_color), None)
                if owned_bullet:
                    break
            if owned_bullet:
                break
        else:
            raise AssertionError("射击后未生成玩家颜色的子弹")
        assert all(key in owned_bullet for key in ("vx", "vy", "owner", "age")), "子弹速度、发射者或弹龄没有同步到客户端"
        await second.close()
        for _ in range(20):
            state = json.loads((await first.receive()).data)
            if len(state.get("players", [])) == 1 and len(state.get("pickups", [])) == 1:
                break
        else:
            raise AssertionError("玩家离开后道具数量没有同步减少")
        await first.close()

        items = await session.ws_connect(f"{base_url}/ws")
        await items.send_json({"name": "道具测试", "room": f"I{run_id}", "mode": "items"})
        assert json.loads((await items.receive()).data)["mode"] == "items"
        for _ in range(10):
            item_state = json.loads((await items.receive()).data)
            if len(item_state.get("pickups", [])) == 3:
                break
        assert len(item_state["pickups"]) == 3, "多道具模式没有生成三倍道具"
        await items.close()

        pure = await session.ws_connect(f"{base_url}/ws")
        await pure.send_json({"name": "纯净测试", "room": f"P{run_id}", "mode": "pure"})
        assert json.loads((await pure.receive()).data)["mode"] == "pure"
        pure_state = json.loads((await pure.receive()).data)
        assert pure_state["pickups"] == [], "纯净模式仍然生成了道具"
        await pure.close()

        profession = await session.ws_connect(f"{base_url}/ws")
        await profession.send_json({"name": "职业测试", "room": f"R{run_id}", "mode": "profession"})
        profession_welcome = json.loads((await profession.receive()).data)
        assert profession_welcome["mode"] == "profession" and profession_welcome["protocol"] == 9
        waiting = json.loads((await profession.receive()).data)
        pro_player = waiting["players"][0]
        assert not pro_player["ready"] and len(waiting["pickups"]) == 1 and waiting["pickups"][0]["kind"] == "health", "职业选择前状态或血包规则错误"
        await profession.send_json({"type": "select_role", "role": "tank"})
        for _ in range(10):
            pro_state = json.loads((await profession.receive()).data)
            pro_player = pro_state["players"][0]
            if pro_player["ready"]:
                break
        assert pro_player["role"] == "tank" and pro_player["max_hp"] == pro_player["hp"] == 300, "坦克职业属性错误"
        await profession.close()
        print("OK: 六职业、死亡后重新选角、房间聊天及多人同步均正常")


asyncio.run(main())
