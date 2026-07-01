import logging
import os
from datetime import datetime, timedelta, timezone

import config
from sources.base import RawItem

log = logging.getLogger(__name__)

_warned_missing_session = False


async def fetch():
    """Источник материалов из Telegram-каналов через Telethon (юзер-сессия).

    Требует одноразового интерактивного логина (телефон + код), который нельзя
    выполнить в headless-окружении — см. README. Пока сессии нет или источник
    выключен через TELETHON_ENABLED, просто возвращает пустой список.
    """
    global _warned_missing_session

    if not config.TELETHON_ENABLED:
        return []

    if not (config.TELEGRAM_API_ID and config.TELEGRAM_API_HASH):
        log.warning(
            "TELETHON_ENABLED=true, но TELEGRAM_API_ID/TELEGRAM_API_HASH не заданы "
            "— источник Telegram-каналов пропущен"
        )
        return []

    if not config.TELETHON_CHANNELS:
        log.warning("TELETHON_ENABLED=true, но TELETHON_CHANNELS пуст — источник пропущен")
        return []

    if not os.path.exists(config.TELETHON_SESSION_PATH):
        if not _warned_missing_session:
            log.warning(
                "Telethon .session не найден (%s). Источник Telegram-каналов отключён. "
                "См. README — нужен одноразовый интерактивный логин локально.",
                config.TELETHON_SESSION_PATH,
            )
            _warned_missing_session = True
        return []

    from telethon import TelegramClient  # локальный импорт: telethon не обязателен, пока источник выключен

    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.TELETHON_LOOKBACK_HOURS)

    client = TelegramClient(
        config.TELETHON_SESSION_PATH, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH
    )
    async with client:
        for channel in config.TELETHON_CHANNELS:
            try:
                async for message in client.iter_messages(channel, limit=20):
                    if not message.text:
                        continue
                    if message.date and message.date < cutoff:
                        break
                    items.append(
                        RawItem(
                            title=message.text.split("\n")[0][:120],
                            description=message.text,
                            content=message.text,
                            url=f"tg://{channel}/{message.id}",
                            source_type="telethon",
                            source_name=channel,
                            image_url=None,
                            published_at=message.date.isoformat() if message.date else None,
                            category="broad",
                        )
                    )
            except Exception as e:
                log.error(f"Telethon error for channel '{channel}': {e}")

    return items
