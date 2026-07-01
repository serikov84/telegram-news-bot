import asyncio
import logging
import time

from telegram import Bot
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
from bot import handlers, scheduler
from processing import image as image_gen
from processing import rewrite as rewriter
from publishers.telegram_publisher import CHANNEL_KEY
from sources import cases_source, newsapi_source, rss_source, telethon_source
from tracking.db import init_db
from tracking.repository import PendingRepo, PublishedRepo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


async def fetch_all_items():
    items = []
    items += newsapi_source.fetch()
    items += rss_source.fetch()
    items += cases_source.fetch()
    if config.TELETHON_ENABLED:
        items += await telethon_source.fetch()
    return items


async def send_for_approval(bot: Bot, item, text):
    """Отправляет черновик апруверу (USER_ID) с кнопками Edit/Approve/Skip."""
    item_id = str(int(time.time() * 1_000_000) % 1_000_000)
    image_url = item.image_url or image_gen.generate_image(item.title)
    PendingRepo.add(item_id, item, text)

    if item.url.startswith("http"):
        message_text = (
            f'{text[:900]}\n\n📰 Источник: {item.source_name}\n'
            f'🔗 <a href="{item.url}">Оригинал</a>'
        )
    else:
        message_text = f"{text[:900]}\n\n📁 Источник: {item.source_name}"

    keyboard = handlers.approval_keyboard(item_id)

    try:
        if image_url:
            await bot.send_photo(
                chat_id=config.USER_ID,
                photo=image_url,
                caption=message_text,
                parse_mode="HTML",
            )
            await bot.send_message(
                chat_id=config.USER_ID, text="Выберите действие:", reply_markup=keyboard
            )
        else:
            await bot.send_message(
                chat_id=config.USER_ID,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        return True
    except Exception as e:
        log.error(f"Ошибка отправки: {e}")
        PendingRepo.delete(item_id)
        return False


async def run_pipeline(bot: Bot):
    """Источники → рерайт через Claude → отправка на одобрение."""
    log.info("📰 Проверка источников...")
    items = await fetch_all_items()

    if not items:
        log.info("Новых материалов не найдено")
        return

    already_published = PublishedRepo.published_urls(CHANNEL_KEY)
    sent_count = 0

    for item in items:
        if sent_count >= config.POSTS_PER_RUN:
            break
        if item.url in already_published:
            continue

        log.info(f"🔄 Обрабатываю: {item.title[:60]}...")
        text = rewriter.rewrite(item)
        if not text:
            log.warning("Не удалось обработать материал")
            continue

        if await send_for_approval(bot, item, text):
            sent_count += 1
            log.info(f"✅ Отправлено для одобрения: {item.title[:60]}")
            await asyncio.sleep(2)

    log.info(f"✅ Готово! Отправлено {sent_count} материалов для одобрения")


async def main():
    init_db()
    scheduler.load_schedule()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", handlers.start_cmd))
    app.add_handler(CommandHandler("schedule", handlers.schedule_cmd))
    app.add_handler(CallbackQueryHandler(handlers.button_handler))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text_message)
    )

    async with app:
        await app.start()
        log.info("🤖 Бот запущен!")

        bot = app.bot

        await run_pipeline(bot)

        asyncio.create_task(scheduler.run_loop(lambda: run_pipeline(bot)))

        if scheduler.schedule_config["enabled"]:
            log.info(f"📅 Расписание включено: {', '.join(scheduler.schedule_config['times'])}")
        else:
            log.info("📅 Расписание отключено")

        await app.updater.start_polling()
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
