# 迁移对照表

| 旧项目 | 统一项目 | 说明 |
| --- | --- | --- |
| `版本1/server.py` | `backend/app/game/engine.py` | 互联网版核心战斗与房间基线，统一由 `APP_EDITION` 配置运行 |
| `版本1_本地版/server.py` | `backend/app/config.py` + `scripts/start_local.ps1` | 局域网监听和 30 帧配置 |
| `霓虹乱斗离线版/server.py` | `backend/app/bots/` + `scripts/start_offline.ps1` | 离线能力入口预留，旧人机算法仍需下一阶段抽取 |
| 各版本 `public/` | `frontend/src/components`、`frontend/src/network`、`frontend/src/styles` | Vue 组件、协议客户端和样式职责拆分 |
| 各版本启动脚本 | `scripts/start_*.ps1` | 统一从环境变量选择运行版本，不提交公网凭据 |

旧目录暂保留为行为对照和回归基线，业务开发入口切换到 `neon-brawl/`。
