import os

APP_EDITION = os.environ.get("APP_EDITION", "internet")
HOST = os.environ.get("HOST", "127.0.0.1" if APP_EDITION == "offline" else "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
PROTOCOL_VERSION = 13
NETWORK_RATE = int(os.environ.get("NETWORK_RATE", "30" if APP_EDITION != "internet" else "25"))
