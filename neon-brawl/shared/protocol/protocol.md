# 霓虹乱斗协议 v13

WebSocket 地址为 `/ws`，消息使用 UTF-8 JSON。HTTP `GET /health` 返回 `status`、`edition`、`protocol`；`GET /config` 返回地图尺寸与能力开关。

客户端消息：

- `join`: `name`、`room`、`mode`
- `input`: `seq`、`move_x`、`move_y`、`angle`、`shoot`、`ability`
- `role`: `role`
- `chat`: `message`
- `bots`: `count`、`difficulty`，仅 offline
- `ping`: `sent`

服务端消息：`welcome`（含 `player_id`、`room`、`mode`、`edition`、`obstacles`）、`state`、`chat`、`pong`、`error`。状态帧通过 `destroyed` 发送增量地形变化，初始地形只在 `welcome` 发送。

所有文本在 Vue 模板中按文本节点渲染；昵称最多 12 字符，聊天最多 120 字符且按空白折叠，输入序号必须递增。
