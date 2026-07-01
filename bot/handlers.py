import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from bot import scheduler
from publishers.telegram_publisher import CHANNEL_KEY, publish as publish_telegram
from tracking.repository import PublishedRepo

log = logging.getLogger(__name__)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Добро пожаловать! Публикую материалы в канал автоматически. "
        "После каждой публикации присылаю вам копию с кнопкой 🗑️, чтобы можно было "
        "быстро удалить пост из канала, если что-то пошло не так."
    )


def undo_keyboard(publish_id):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🗑️ Удалить из канала", callback_data=f"undo_{publish_id}")]]
    )


async def notify_published(bot: Bot, text, publish_id):
    """Теневое уведомление апруверу после автопубликации — страховка на случай неудачного текста."""
    notice = f"🤖 Опубликовано автоматически:\n\n{text[:900]}"
    try:
        await bot.send_message(
            chat_id=config.USER_ID, text=notice, reply_markup=undo_keyboard(publish_id)
        )
    except Exception as e:
        log.error(f"Не удалось отправить теневое уведомление: {e}")


async def publish_and_notify(bot: Bot, item, text, image_url):
    """Публикует материал в канал, логирует в tracking и шлёт теневое уведомление апруверу."""
    try:
        message = await publish_telegram(bot, text, image_url, item.url)
    except Exception as e:
        log.error(f"Ошибка публикации: {e}")
        return False

    publish_id = PublishedRepo.add(
        source_type=item.source_type,
        source_url=item.url,
        channel=CHANNEL_KEY,
        title=item.title,
        text=text,
        image_url=image_url,
        channel_message_id=message.message_id,
    )

    await notify_published(bot, text, publish_id)
    return True


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок: отмена публикации и управление расписанием"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("undo_"):
        publish_id = int(data.split("_", 1)[1])
        record = PublishedRepo.get(publish_id)
        if not record:
            await query.edit_message_text("Пост не найден.")
            return
        if record["deleted_at"]:
            await query.edit_message_text("Пост уже удалён из канала.")
            return

        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        try:
            await bot.delete_message(
                chat_id=config.TELEGRAM_CHANNEL, message_id=record["channel_message_id"]
            )
            PublishedRepo.mark_deleted(publish_id)
            await query.edit_message_text("🗑️ Пост удалён из канала.")
            log.info(f"Undo: {record['title'][:60] if record['title'] else publish_id}")
        except Exception as e:
            log.error(f"Не удалось удалить пост: {e}")
            await query.edit_message_text(f"❌ Ошибка удаления: {e}")
        return

    if data == "sched_show":
        status = "✅ Включено" if scheduler.schedule_config["enabled"] else "❌ Отключено"
        times = ", ".join(scheduler.schedule_config["times"])
        await query.edit_message_text(f"📋 Статус: {status}\n⏰ Время: {times}")
        return

    if data == "sched_on":
        scheduler.schedule_config["enabled"] = True
        scheduler.save_schedule()
        await query.edit_message_text("✅ Расписание включено!")
        return

    if data == "sched_off":
        scheduler.schedule_config["enabled"] = False
        scheduler.save_schedule()
        await query.edit_message_text("❌ Расписание отключено!")
        return

    if data == "sched_set":
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "09:00, 13:00, 18:00, 20:00", callback_data="time_default"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "08:00, 12:00, 17:00, 21:00", callback_data="time_alt1"
                    )
                ],
                [InlineKeyboardButton("10:00, 14:00, 19:00", callback_data="time_alt2")],
            ]
        )
        await query.edit_message_text("⏰ Выберите расписание:", reply_markup=keyboard)
        return

    if data.startswith("time_"):
        preset = data.split("_", 1)[1]
        presets = {
            "default": ["09:00", "13:00", "18:00", "20:00"],
            "alt1": ["08:00", "12:00", "17:00", "21:00"],
            "alt2": ["10:00", "14:00", "19:00"],
        }
        new_times = presets.get(preset, presets["default"])
        scheduler.schedule_config["times"] = new_times
        scheduler.schedule_config["enabled"] = True
        scheduler.save_schedule()
        await query.edit_message_text(f"⏰ Расписание установлено:\n{', '.join(new_times)}")
        return


async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /schedule"""
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Показать статус", callback_data="sched_show")],
            [
                InlineKeyboardButton("✅ Включить", callback_data="sched_on"),
                InlineKeyboardButton("❌ Отключить", callback_data="sched_off"),
            ],
            [InlineKeyboardButton("⏰ Установить время", callback_data="sched_set")],
        ]
    )
    await update.message.reply_text(
        "⚙️ Управление расписанием:\n\nНажмите на кнопку чтобы изменить настройки",
        reply_markup=keyboard,
    )
