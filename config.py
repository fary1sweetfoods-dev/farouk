import os

# CRT Bot Credentials (@Candle_rangebot)
CRT_BOT_TOKEN = os.getenv("CRT_BOT_TOKEN", "8207903110:AAGYczgakx60v5Xs2ZUCQCjwSDjOo8ebvd0")
CRT_CHAT_ID = os.getenv("CRT_CHAT_ID", "6052212943")

# Aliases for compatibility
ALPHA_BOT_TOKEN = CRT_BOT_TOKEN
ALPHA_CHAT_ID = CRT_CHAT_ID

# Asset Watchlist
WATCHLIST = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDJPY",
    "USDCAD", "GBPCAD", "GBPJPY", "XAUUSD"
]

# Global Configuration Dictionary
CONFIG = {
    "min_rr": 2.0,
    "scan_interval": 60
}