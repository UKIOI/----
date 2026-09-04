from .game.engine import app

__all__ = ["app"]

if __name__ == "__main__":
    import os
    from aiohttp import web

    host = os.environ.get("HOST", "127.0.0.1" if os.environ.get("APP_EDITION") == "offline" else "0.0.0.0")
    web.run_app(app, host=host, port=int(os.environ.get("PORT", "8080")))
