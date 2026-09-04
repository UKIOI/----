# 霓虹乱斗前后端分离版

统一迁移目录，旧的三个版本仅用于对照。后端是 Python/aiohttp，前端是 Vue 3 + TypeScript + Vite。

## 开发

后端：

```powershell
cd backend
python -m pip install -r requirements.txt
$env:APP_EDITION = 'local'
python -m app.main
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

开发服务器默认将 `/ws`、`/health` 和 `/config` 代理到 `127.0.0.1:8080`。生产环境使用 `VITE_API_BASE_URL` 指向独立后端，HTTPS 会自动使用 WSS。

## 三种运行模式

`APP_EDITION=internet` 监听 `0.0.0.0`、25 帧网络广播；`local` 同样提供局域网访问、30 帧广播；`offline` 默认监听 `127.0.0.1`，并保留人机配置入口。启动脚本位于 `scripts/`，敏感隧道凭据只从本机环境或 FRP 配置读取。

## 验证

```powershell
python -m compileall backend/app
```

前端构建需要 Node.js 和 npm：`npm run build`。
