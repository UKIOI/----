import asyncio
import json
import os
import time
import uuid

import aiohttp

from server import COLORS, Room, finite_number, ray_rect_hit


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
    assert finite_number("bad", 3) == 3 and finite_number(float("nan"), 4) == 4, "异常输入数字没有安全回退"
    unit_room.task.cancel()

    motion_room = Room("MOTION_UNIT")
    motion_now = time.monotonic()
    motion_player = {"id": "motion", "name": "移动", "x": 100, "y": 100, "hp": 100, "max_hp": 100,
                     "score": 0, "color": "#fff", "last_shot": 0, "respawn": 0, "effects": {},
                     "minions": [], "role": None, "ready": True, "next_weapon": 0,
                     "ability_ready": 0, "master_weapon": None, "last_input": motion_now,
                     "input": {"up": False, "down": False, "left": False, "right": False,
                               "move_x": 0.5, "move_y": 0, "shoot": False, "ability": False, "angle": 0}}
    motion_room.players = {"motion": motion_player}
    motion_room.update(0.1, motion_now)
    assert abs(motion_player["x"] - 115) < 0.01, "模拟摇杆力度被错误转换成满速"
    motion_player["last_input"], before_timeout = motion_now - 1, motion_player["x"]
    motion_room.update(0.1, motion_now)
    assert motion_player["x"] == before_timeout and motion_player["input"]["move_x"] == 0, "输入超时后玩家仍在移动"
    motion_room.task.cancel()

    ai_room = Room("AI_UNIT", "pure")
    ai_now = time.monotonic()
    ai_human = {"id": "human", "name": "目标", "x": 560, "y": 170, "hp": 100, "max_hp": 100,
                "score": 0, "color": "#fff", "effects": {}, "ready": True, "role": None,
                "input": {"move_x": 0, "move_y": 0}}
    ai_room.players = {"human": ai_human}
    ai_room.sync_solo_bot()
    hard_bot = ai_room.bots()[0]
    hard_bot.update(x=200, y=170, hp=100, bot_next_think=0)
    ai_room.update_bots(ai_now)
    assert hard_bot["bot_goal_kind"] == "chase" and abs(hard_bot["input"]["move_y"]) > .1, "困难人机不会绕过阻挡路线的地形"
    hard_bot.update(x=200, y=100, bot_next_think=0)
    ai_human.update(x=600, y=100)
    ai_room.bullets = [{"owner": "human", "x": 40, "y": 100, "vx": 760, "vy": 0, "radius": 6}]
    ai_room.update_bots(ai_now + 1)
    assert hard_bot["bot_goal_kind"] == "dodge" and abs(hard_bot["input"]["move_y"]) > .5, "困难人机不会预判躲避来袭子弹"
    ai_room.bullets.clear()
    hard_bot["bot_next_think"] = 0
    ai_human["input"].update(move_x=0, move_y=1)
    ai_room.update_bots(ai_now + 2)
    assert hard_bot["input"]["angle"] > .2, "困难人机不会对移动目标计算射击提前量"
    ai_room.task.cancel()

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
    assert paladin["hp"] == 100 and paladin["effects"]["invincible"] == now + 7 and paladin["effects"]["speed"] == now + 7 and paladin["ability_ready"] == now + 20, "圣骑士无敌、加速或冷却错误"
    class_room.task.cancel()

    upgrade_room = Room("UPGRADE_UNIT", "upgrade")
    upgrade_player = {"id": "upgrader", "name": "升级者", "x": 100, "y": 100, "hp": 70, "max_hp": 100,
                      "score": 1, "color": "#72f1d0", "last_shot": 0, "respawn": 0, "effects": {},
                      "minions": [], "role": None, "ready": True, "is_bot": False, "level": 1,
                      "upgrades": {}, "upgrade_choices": [],
                      "input": {"up": False, "down": False, "left": False, "right": False,
                                "move_x": 0, "move_y": 0, "shoot": False, "ability": False, "angle": 0}}
    upgrade_room.players = {"upgrader": upgrade_player}
    upgrade_room.check_level_up(upgrade_player)
    assert upgrade_player["level"] == 2 and len(upgrade_player["upgrade_choices"]) == 3, "首次升级没有提供三个强化选项"
    upgrade_player["upgrade_choices"] = ["vitality"]
    assert upgrade_room.apply_upgrade(upgrade_player, "vitality")
    assert upgrade_player["max_hp"] == 115 and upgrade_player["hp"] == 85 and upgrade_player["upgrades"]["vitality"] == 1, "生命强化数值错误"
    assert [upgrade_room.next_level_score(level) for level in range(1, 6)] == [1, 3, 6, 10, 15], "升级经验曲线不是逐级提高"
    upgrade_player["upgrades"].update(power=3, haste=3, agility=3, velocity=3, arsenal=2)
    upgrade_player["input"].update(move_x=1, shoot=True)
    upgrade_player["last_shot"] = 0
    upgrade_now, upgrade_start_x = time.monotonic(), upgrade_player["x"]
    upgrade_room.update(.1, upgrade_now)
    assert abs(upgrade_player["x"] - upgrade_start_x - 35.4) < .01, "升级模式移速强化数值错误"
    assert len(upgrade_room.bullets) == 3, "武器扩展没有生成三发子弹"
    assert all(abs(bullet["damage"] - 23.4) < .01 and abs((bullet["vx"] ** 2 + bullet["vy"] ** 2) ** .5 - 988) < .1 for bullet in upgrade_room.bullets), "火力、弹速或多发平衡数值错误"
    upgrade_room.update(.01, upgrade_now + .18)
    assert len(upgrade_room.bullets) == 6, "快速装填没有缩短射击间隔"
    upgrade_room.task.cancel()

    bio_room = Room("BIO_UNIT", "bio")
    bio_player = {**upgrade_player, "id": "survivor", "name": "幸存者", "hp": 100, "max_hp": 100,
                  "score": 0, "xp": 0, "level": 1, "upgrades": {}, "upgrade_choices": [],
                  "effects": {}, "minions": [], "input": {**upgrade_player["input"], "shoot": False, "move_x": 0}}
    bio_room.players = {"survivor": bio_player}
    bio_room.sync_solo_bot()
    assert bio_room.width == 2800 and bio_room.height == 1800 and len(bio_room.terrain) > len(unit_room.terrain), "生化模式没有使用大型复杂地图"
    assert not bio_room.bots(), "生化模式错误加入了对战困难人机"
    bio_now = time.monotonic()
    bio_room.start_bio_wave(bio_now)
    assert bio_room.wave == 1 and bio_room.wave_active and len(bio_room.zombies) >= 7, "生化模式首波没有生成足够僵尸"
    zombie = bio_room.zombies[0]
    bio_room.damage_zombie(zombie, zombie["hp"], "survivor", bio_now)
    assert bio_player["score"] == 1 and bio_player["xp"] == zombie["xp"], "击杀僵尸没有获得击杀数或经验"
    teammate = {**bio_player, "id": "teammate", "name": "队友", "x": bio_player["x"] + 50, "hp": 100,
                "score": 0, "xp": 0, "upgrade_choices": [], "input": {**bio_player["input"]}}
    bio_room.players["teammate"] = teammate
    bio_room.zombies = []
    bio_room.wave_active, bio_room.next_wave = False, bio_now + 100
    bio_room.add_bullet({"x": teammate["x"], "y": teammate["y"], "vx": 1, "vy": 0, "owner": "survivor",
                         "color": "#fff", "damage": 99, "damage_type": "normal", "radius": 6,
                         "kind": "bullet", "bounces": 0, "life": 1, "created": bio_now})
    bio_room.update(.01, bio_now + .1)
    assert teammate["hp"] == 100, "生化合作模式仍存在队友伤害"
    bio_room.add_bullet({"x": teammate["x"], "y": teammate["y"], "vx": 1, "vy": 0, "owner": "z999",
                         "color": "#9cff57", "damage": 10, "damage_type": "normal", "radius": 7,
                         "kind": "zombie", "bounces": 0, "life": 1, "created": bio_now})
    bio_room.update(.01, bio_now + .2)
    assert teammate["hp"] == 90, "僵尸远程弹没有伤害玩家"
    bio_room.wave, bio_room.zombies = 4, []
    bio_room.start_bio_wave(bio_now + 1)
    assert bio_room.wave == 5 and any(zombie["boss"] and zombie["kind"] in {"plague_lord", "brood_queen", "iron_abomination"} for zombie in bio_room.zombies), "第五波没有刷新随机 Boss"
    bio_room.task.cancel()

    bio_scale_room = Room("BIO_SCALE", "bio")
    bio_scale_room.players = {"one": bio_player, "two": {**bio_player, "id": "two", "name": "队友"}}
    bio_scale_room.start_bio_wave(bio_now)
    assert len(bio_scale_room.zombies) > 7 and max(zombie["max_hp"] for zombie in bio_scale_room.zombies) > 65, "联机人数没有提高生化波次数量和生命强度"
    bio_scale_room.task.cancel()
    base_url = f"http://127.0.0.1:{os.environ.get('TEST_PORT', '8080')}"
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/health") as response:
            health = await response.json()
            assert health == {"game": "neon-brawl", "edition": "internet", "status": "ok", "protocol": 16, "build": 43}, "互联网版健康检查标识错误"
        async with session.get(f"{base_url}/rooms") as response:
            assert await response.json() == {"rooms": []}, "空服务器的公开房间列表不正确"
        async with session.get(f"{base_url}/") as response:
            assert response.status == 200
            page = await response.text()
            assert "霓虹乱斗" in page and 'viewport-fit=cover' in page and 'id="rotateNotice"' in page, "横屏安全区界面未加载"
            assert 'data-role="weaponmaster"' in page and 'data-role="paladin"' in page and 'id="skillButton"' in page, "新职业界面未加载"
            assert 'id="joystick"' in page and 'id="aimJoystick"' in page, "手机双轮盘界面未加载"
            assert 'id="chatToggle"' in page and 'id="chatPanel"' in page and 'id="chatForm"' in page and 'id="soundToggle"' in page, "折叠聊天或音效界面未加载"
            assert 'id="roomBrowserToggle"' in page and 'id="roomBrowser"' in page and 'id="roomList"' in page, "公开房间列表界面未加载"
            assert 'id="guideToggle"' in page and 'id="guidePanel"' in page and 'id="guideClose"' in page, "玩法说明界面未加载"
            assert all(text in page for text in ("困难人机", "经典模式", "攻城大炮", "武器大师", "手机横屏和竖屏均可玩")), "玩法说明缺少重要规则"
            assert 'option value="upgrade"' in page and 'id="upgrades"' in page and 'id="upgradeChoices"' in page, "升级模式入口或选择面板未加载"
            assert "升级模式强化" in page and "无敌并加速 7 秒" in page, "升级模式或圣骑士新规则未写入玩法说明"
            assert 'option value="bio"' in page and "生化模式" in page and "瘟疫领主" in page and "钢铁畸变体" in page, "生化模式入口或玩法说明未加载"
            assert '/static/style.css?v=17' in page and '/static/game.js?v=43' in page, "客户端缓存版本未更新"
            assert response.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate, max-age=0", "入口页没有禁止旧客户端缓存"
        async with session.get(f"{base_url}/static/style.css?v=17") as response:
            mobile_style = await response.text()
            assert '@media (orientation: portrait)' in mobile_style and 'html.mobile-controls #rotateNotice { display: none; }' in mobile_style, "手机竖屏可玩布局未加载"
            assert 'width: min(116px, 29vw)' in mobile_style and 'height: min(52vh, 390px)' in mobile_style, "竖屏轮盘或聊天布局未适配"
        async with session.get(f"{base_url}/static/game.js?v=43") as response:
            mobile_script = await response.text()
            assert response.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate, max-age=0", "客户端脚本没有禁止缓存"
            assert "visualViewport" in mobile_script and "viewWidth" in mobile_script and "orientationchange" in mobile_script, "动态横屏适配脚本未加载"
            assert "viewScale" in mobile_script and "viewHeight > viewWidth ? .62 : .72" in mobile_script and "motionTracks" in mobile_script and "function visible" in mobile_script, "移动端横竖屏视野或性能优化未加载"
            assert "speedTrailAnchors" in mobile_script and "recordSpeedTrails(displayPlayers, now)" in mobile_script and "drawSpeedTrails(now)" in mobile_script and "/ 220" in mobile_script, "加速残影未跟随最终渲染坐标或仍然过长"
            assert "touchMove" in mobile_script and "touchAim" in mobile_script and 'aimJoystick.addEventListener("pointerdown"' in mobile_script, "双轮盘输入脚本未加载"
            assert "KEY_CODES" in mobile_script and "sendInput(performance.now(), true)" in mobile_script, "公网键盘兼容输入脚本未加载"
            assert "appendChatMessage" in mobile_script and "message.textContent" in mobile_script and "stopGameInput" in mobile_script, "安全聊天或输入隔离脚本未加载"
            assert all(marker in mobile_script for marker in ("AudioContext", "playStateSounds", "playEffect", "neon-sound")), "游戏音效系统未加载"
            assert "unreadChats > 9" in mobile_script and 'chatUnread.textContent = "0"' in mobile_script, "聊天未读红点计数未加载"
            assert "new Map(data.destroyed" in mobile_script, "增量地形同步脚本未加载"
            assert "updateLocalPrediction" in mobile_script and "reconcilePrediction" in mobile_script and "updateLatency" in mobile_script, "本机移动预测或延迟检测脚本未加载"
            assert "lastStopSequence" in mobile_script and "inputSequence" in mobile_script, "停止输入确认脚本未加载"
            assert "stateReceivedAt" in mobile_script and "bulletX" in mobile_script and "drawProjectiles(now)" in mobile_script, "子弹帧间预测脚本未加载"
            assert "REMOTE_INTERPOLATION_MS" in mobile_script and "synchronizedSnapshotTime" in mobile_script and "sampledMotionPoint" in mobile_script, "远端实体时间轴插值未加载"
            assert "BULLET_EXTRAPOLATION_MS" in mobile_script and "sampledBulletPoint" in mobile_script and "error <= .75" in mobile_script, "公网子弹连续预测或停止柔性校正未加载"
            assert "extrapolatedBulletPosition" in mobile_script, "子弹预测缺少墙体碰撞限制"
            assert all(marker in mobile_script for marker in ("sampledBulletPoint", "aimOrigin", "move_x", "input_seq", "baseLead", "perpendicular", "ws.bufferedAmount")), "移动、停止确认、瞄准或匀速校正优化未加载"
            assert "stop_x" not in mobile_script and "predictionHoldUntil" not in mobile_script, "旧的停止补位逻辑仍在客户端"
            assert "event.repeat" in mobile_script and "visibilitychange" in mobile_script, "卡键和页面后台输入保护未加载"
            assert all(marker in mobile_script for marker in ('refreshRoomBrowser', 'fetch("/rooms"', 'room.players', 'room.mode')), "公开房间列表读取或选择逻辑未加载"
            assert all(marker in mobile_script for marker in ("BUILD_VERSION = 43", "neon-protocol-refresh", "location.replace", "主机仍在运行旧版服务器", "该房间已使用其他玩法模式")), "版本自动刷新、构建检查或模式错误提示未加载"
            assert all(marker in mobile_script for marker in ("openGuide", "closeGuide", "guidePanel.hidden")), "玩法说明打开或关闭逻辑未加载"
            assert all(marker in mobile_script for marker in ("UPGRADE_INFO", "updateUpgradePanel", "select_upgrade", "next_level_score", "[Lv.${p.level")), "升级选择、经验显示或等级名称未加载"
            assert all(marker in mobile_script for marker in ("exploredBioCells", "drawBioFog", "drawBioMinimap", "drawZombies", "drawBioWaveHud")), "生化模式迷雾、小地图、僵尸或波次界面未加载"

        first = await session.ws_connect(f"{base_url}/ws")
        second = await session.ws_connect(f"{base_url}/ws")
        await first.send_json({"name": "A", "room": run_id})
        await second.send_json({"name": "B", "room": run_id})
        first_welcome = json.loads((await first.receive()).data)
        second_welcome = json.loads((await second.receive()).data)
        assert first_welcome["room"] == run_id and second_welcome["room"] == run_id
        assert first_welcome["protocol"] == 16 and first_welcome["build"] == 43 and first_welcome["edition"] == "internet" and len(first_welcome["obstacles"]) > 8, "初始地形、构建版本或压缩协议未发送"
        for _ in range(20):
            state = json.loads((await first.receive()).data)
            player_names = {player["name"] for player in state.get("players", [])}
            if state.get("type") == "state" and player_names == {"A", "B"} and not any(player.get("bot") for player in state["players"]):
                break
        else:
            raise AssertionError("两个客户端未收到同一房间的状态")
        assert len(state["pickups"]) == len(state["players"]) == 2, "道具数量没有跟随在线人数"
        assert not any(player.get("bot") for player in state["players"]), "两名真人在线时困难人机没有消失"
        async with session.get(f"{base_url}/rooms") as response:
            listed_rooms = (await response.json())["rooms"]
        listed_room = next((room for room in listed_rooms if room["code"] == run_id), None)
        assert listed_room == {"code": run_id, "mode": "classic", "players": 2, "bots": 0, "capacity": 12}, "公开房间的模式或人数不正确"
        assert isinstance(state.get("server_time"), (int, float)), "状态帧缺少服务器时间戳"
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
            raise AssertionError("公网延迟检测没有收到响应")
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
        await first.send_json({"type": "input", "seq": 40, "right": True, "move_x": 0.5, "move_y": 0, "angle": 0})
        moved = False
        for _ in range(20):
            state = json.loads((await first.receive()).data)
            player = next((p for p in state.get("players", []) if p["name"] == "A"), None)
            if player and player["x"] > before:
                moved = True
                break
        assert moved, "服务端没有处理移动输入"
        await first.send_json({"type": "input", "seq": 41, "move_x": 0, "move_y": 0, "angle": 0})
        for _ in range(10):
            stopped_state = json.loads((await first.receive()).data)
            stopped_player = next((p for p in stopped_state.get("players", []) if p["name"] == "A"), None)
            if stopped_player and stopped_player["move_x"] == stopped_player["move_y"] == 0 and stopped_player["input_seq"] == 41:
                break
        else:
            raise AssertionError("服务器没有确认停止移动")
        stopped_x = stopped_player["x"]
        await first.send_json({"type": "input", "seq": 40, "move_x": 1, "move_y": 0, "angle": 0})
        for _ in range(3):
            stale_state = json.loads((await first.receive()).data)
            if stale_state.get("type") == "state":
                stale_player = next(p for p in stale_state["players"] if p["name"] == "A")
        assert stale_player["input_seq"] == 41 and abs(stale_player["x"] - stopped_x) < 0.2, "过期移动输入导致停止后继续位移"
        await first.send_json({"type": "input", "seq": 42, "move_x": "bad", "move_y": None, "angle": "bad"})
        for _ in range(5):
            safe_state = json.loads((await first.receive()).data)
            if safe_state.get("type") == "state":
                break
        assert safe_state["type"] == "state", "异常输入导致连接断开"
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
        assert all(key in owned_bullet for key in ("id", "vx", "vy", "owner", "age")), "子弹稳定标识、速度、发射者或弹龄没有同步到客户端"
        await second.close()
        solo_bot = None
        for _ in range(30):
            state = json.loads((await first.receive()).data)
            solo_bot = next((player for player in state.get("players", []) if player.get("bot")), None)
            if len(state.get("players", [])) == 2 and len(state.get("pickups", [])) == 2 and solo_bot and abs(solo_bot["move_x"]) + abs(solo_bot["move_y"]) > 0:
                break
        else:
            raise AssertionError("房间只剩一名真人后没有自动加入困难人机")
        assert solo_bot["name"] == "困难人机" and solo_bot["bot_difficulty"] == "hard", "自动人机没有使用困难强度"
        await first.close()

        items = await session.ws_connect(f"{base_url}/ws")
        await items.send_json({"name": "道具测试", "room": f"I{run_id}", "mode": "items"})
        assert json.loads((await items.receive()).data)["mode"] == "items"
        for _ in range(10):
            item_state = json.loads((await items.receive()).data)
            if len(item_state.get("pickups", [])) == 6 and any(player.get("bot") for player in item_state.get("players", [])):
                break
        assert len(item_state["pickups"]) == 6, "单人加困难人机后多道具模式没有按参战人数生成三倍道具"
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
        assert profession_welcome["mode"] == "profession" and profession_welcome["protocol"] == 16
        waiting = json.loads((await profession.receive()).data)
        pro_player = waiting["players"][0]
        assert not pro_player["ready"] and len(waiting["pickups"]) == 2 and all(pickup["kind"] == "health" for pickup in waiting["pickups"]), "职业选择前状态、困难人机或血包规则错误"
        await profession.send_json({"type": "select_role", "role": "tank"})
        for _ in range(10):
            pro_state = json.loads((await profession.receive()).data)
            pro_player = pro_state["players"][0]
            if pro_player["ready"]:
                break
        assert pro_player["role"] == "tank" and pro_player["max_hp"] == pro_player["hp"] == 300, "坦克职业属性错误"
        await profession.close()

        upgrade = await session.ws_connect(f"{base_url}/ws")
        await upgrade.send_json({"name": "升级测试", "room": f"U{run_id}", "mode": "upgrade"})
        upgrade_welcome = json.loads((await upgrade.receive()).data)
        assert upgrade_welcome["mode"] == "upgrade" and upgrade_welcome["protocol"] == 16
        for _ in range(10):
            upgrade_state = json.loads((await upgrade.receive()).data)
            upgrade_human = next((p for p in upgrade_state.get("players", []) if not p.get("bot")), None)
            if upgrade_human and len(upgrade_state.get("pickups", [])) == 2:
                break
        assert upgrade_human["level"] == 1 and upgrade_human["next_level_score"] == 1 and upgrade_human["upgrades"] == {}, "升级模式初始等级数据错误"
        assert all(pickup["kind"] == "health" for pickup in upgrade_state["pickups"]), "升级模式生成了血包以外的道具"
        await upgrade.close()

        bio = await session.ws_connect(f"{base_url}/ws")
        await bio.send_json({"name": "生化测试", "room": f"Z{run_id}", "mode": "bio"})
        bio_welcome = json.loads((await bio.receive()).data)
        assert bio_welcome["mode"] == "bio" and bio_welcome["width"] == 2800 and bio_welcome["height"] == 1800
        bio_state = json.loads((await bio.receive()).data)
        assert bio_state["bio"]["wave"] == 0 and bio_state["bio"]["next_wave"] > 0 and not any(player.get("bot") for player in bio_state["players"]), "生化模式初始倒计时或合作房间人机规则错误"
        assert "zombies" in bio_state and bio_state["players"][0]["next_level_score"] == 4, "生化僵尸同步或经验曲线错误"
        await bio.close()
        launcher_script = (os.path.join(os.path.dirname(__file__), "start_internet.ps1"))
        with open(launcher_script, encoding="utf-8-sig") as launcher_file:
            launcher_text = launcher_file.read()
        assert "[房间人数]" in launcher_text and "latestRoomStatus" in launcher_text, "互联网主机窗口没有显示房间人数"
        print("OK: 生化波次、三类Boss、探索迷雾、升级模式及多人同步均正常")


asyncio.run(main())
