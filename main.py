import asyncio
import logging
from datetime import datetime, timezone

from telegram import Bot
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

import config
from bot import handlers, scheduler
from processing import image as image_gen
from processing import rewrite as rewriter
from publishers.telegram_publisher import CHANNEL_KEY
from sources import cases_source, newsapi_source, rss_source, telethon_source
from tracking.db import init_db
from tracking.repository import PublishedRepo

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


async def run_pipeline(bot: Bot):
    """Источники → рерайт через Claude → автопубликация в канал (+ теневое уведомление)."""
    log.info("📰 Проверка источников...")
    items = await fetch_all_items()

    if not items:
        log.info("Новых материалов не найдено")
        return

    already_published = PublishedRepo.published_urls(CHANNEL_KEY)
    today_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
    published_today = PublishedRepo.count_since(CHANNEL_KEY, today_start)

    sent_count = 0

    for item in items:
        if sent_count >= config.POSTS_PER_RUN:
            break
        if published_today + sent_count >= config.DAILY_PUBLISH_LIMIT:
            log.info(f"Достигнут дневной лимит публикаций ({config.DAILY_PUBLISH_LIMIT})")
            break
        if item.url in already_published:
            continue

        log.info(f"🔄 Обрабатываю: {item.title[:60]}...")
        text = rewriter.rewrite(item)
        if not text:
            log.warning("Не удалось обработать материал")
            continue

        image_url = item.image_url or image_gen.generate_image(item.title)

        if await handlers.publish_and_notify(bot, item, text, image_url):
            sent_count += 1
            log.info(f"✅ Опубликовано: {item.title[:60]}")
            await asyncio.sleep(2)

    log.info(f"✅ Готово! Опубликовано {sent_count} материалов")


async def main():
    init_db()
    scheduler.load_schedule()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", handlers.start_cmd))
    app.add_handler(CommandHandler("schedule", handlers.schedule_cmd))
    app.add_handler(CallbackQueryHandler(handlers.button_handler))

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
