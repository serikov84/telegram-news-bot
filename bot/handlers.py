import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from bot import scheduler
from publishers.telegram_publisher import CHANNEL_KEY, publish as publish_telegram
from tracking.repository import PendingRepo, PublishedRepo

log = logging.getLogger(__name__)


def approval_keyboard(item_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{item_id}")],
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve_{item_id}"),
                InlineKeyboardButton("❌ Пропустить", callback_data=f"skip_{item_id}"),
            ],
        ]
    )


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Добро пожаловать! Я буду присылать вам материалы на одобрение."
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок одобрения/пропуска и расписания"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("edit_"):
        item_id = data.split("_", 1)[1]
        item = PendingRepo.get(item_id)
        if item:
            context.user_data["editing_item_id"] = item_id
            await query.edit_message_text(f"Отправьте новый текст:\n\n{item['text']}")
        return

    if data.startswith("approve_"):
        item_id = data.split("_", 1)[1]
        item = PendingRepo.get(item_id)
        if not item:
            return

        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        try:
            await publish_telegram(bot, item["text"], item["image_url"], item["source_url"])
            PublishedRepo.add(
                source_type=item["source_type"],
                source_url=item["source_url"],
                channel=CHANNEL_KEY,
                title=item["title"],
                text=item["text"],
                image_url=item["image_url"],
            )
            PendingRepo.delete(item_id)
            await query.edit_message_text("✅ Опубликовано в канал!")
            log.info(f"Published: {item['title'][:60]}")
        except Exception as e:
            log.error(f"Error publishing: {e}")
            await query.edit_message_text(f"❌ Ошибка: {e}")
        return

    if data.startswith("skip_"):
        item_id = data.split("_", 1)[1]
        PendingRepo.delete(item_id)
        await query.edit_message_text("⏭️ Пропущено")
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


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка редактирования текста"""
    item_id = context.user_data.get("editing_item_id")
    if not item_id:
        return
    item = PendingRepo.get(item_id)
    if not item:
        return

    new_text = update.message.text
    PendingRepo.update_text(item_id, new_text)

    await update.message.reply_text(
        "✏️ Текст обновлён! Опубликовать?", reply_markup=approval_keyboard(item_id)
    )


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
