import os

import yaml
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CASES_DIR = os.path.join(BASE_DIR, "cases")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "bot.db")
SCHEDULE_PATH = os.path.join(DATA_DIR, "schedule.json")

# --- Telegram / API ключи ---
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
USER_ID = int(os.getenv("USER_ID", "0"))

# --- Telethon (источник: парсинг Telegram-каналов), по умолчанию выключен ---
TELETHON_ENABLED = os.getenv("TELETHON_ENABLED", "false").lower() == "true"
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELETHON_SESSION_PATH = os.path.join(DATA_DIR, "telethon.session")
TELETHON_CHANNELS = [
    c.strip() for c in os.getenv("TELETHON_CHANNELS", "").split(",") if c.strip()
]
TELETHON_LOOKBACK_HOURS = int(os.getenv("TELETHON_LOOKBACK_HOURS", "24"))


def _load_yaml(filename, default):
    path = os.path.join(BASE_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or default
    except FileNotFoundError:
        return default


_topics = _load_yaml("topics.yaml", {})
BROAD_QUERIES = _topics.get("broad", {}).get("queries", [])
NICHE_QUERIES = _topics.get("niche", {}).get("queries", [])
POSTS_PER_RUN = _topics.get("posts_per_run", 3)
NEWS_LOOKBACK_HOURS = _topics.get("lookback_hours", 24)
DAILY_PUBLISH_LIMIT = _topics.get("daily_publish_limit", 8)

_feeds = _load_yaml("feeds.yaml", {})
RSS_FEEDS = _feeds.get("feeds", []) or []

DEFAULT_SCHEDULE = {"enabled": False, "times": ["09:00", "13:00", "18:00", "20:00"]}
