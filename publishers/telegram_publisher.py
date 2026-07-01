import logging

from telegram import Bot

import config

log = logging.getLogger(__name__)

CHANNEL_KEY = f"telegram:{config.TELEGRAM_CHANNEL}"


async def publish(bot: Bot, text, image_url, source_url):
    post_text = text
    if source_url and source_url.startswith("http"):
        post_text += f'\n\n📰 Источник: <a href="{source_url}">Читать полностью</a>'

    if image_url:
        try:
            return await bot.send_photo(
                chat_id=config.TELEGRAM_CHANNEL,
                photo=image_url,
                caption=post_text[:1024],
                parse_mode="HTML",
            )
        except Exception as e:
            log.warning(f"Не удалось отправить фото, отправляю текстом: {e}")

    return await bot.send_message(
        chat_id=config.TELEGRAM_CHANNEL,
        text=post_text[:4096],
        parse_mode="HTML",
    )
