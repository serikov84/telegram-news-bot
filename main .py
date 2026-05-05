import os
import time
import logging
import requests
import schedule
import json
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
import anthropic
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
import replicate

load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
USER_ID = int(os.getenv("USER_ID", "0"))
log.info(f"USER_ID loaded: {USER_ID}")

SEARCH_QUERIES = [
    "artificial intelligence AI",
    "AI startups",
    "fintech financial technology",
    "cryptocurrency blockchain",
    "digital government services",
    "tax technology",
    "AI investments venture capital",
]
POSTS_PER_RUN = 3
published_urls = set()
pending_articles = {}
schedule_config = {"enabled": False, "times": ["09:00", "13:00", "18:00", "20:00"]}


def save_schedule():
    try:
        with open("schedule.json", "w") as f:
            json.dump(schedule_config, f)
    except:
        pass


def load_schedule():
    global schedule_config
    try:
        with open("schedule.json", "r") as f:
            schedule_config = json.load(f)
    except:
        pass


def fetch_news():
    articles = []
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    for query in SEARCH_QUERIES:
        try:
            r = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "from": yesterday,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": 5,
                    "apiKey": NEWS_API_KEY,
                },
                timeout=10,
            )
            data = r.json()
            for a in data.get("articles", []):
                if a.get("url") and a["url"] not in published_urls:
                    articles.append(a)
        except Exception as e:
            log.error(f"NewsAPI error: {e}")

    seen = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique


def rewrite_article(article):
    """Переписывает статью на русский через Claude"""
    try:
        title = article.get("title", "")
        description = article.get("description", "")
        content = article.get("content", "")

        prompt = f"""Переписать эту новость на русском языке как пост для Telegram канала. 
Требования:
- 2-5 абзацев
- Без # в начале текста
- Без эмодзи и символов
- Без хэштегов 
- Добавить детали и факты из оригинальной новости
- Первая строка - краткий заголовок жирным шрифтом
- Последний абзац - краткое резюме новости

Новость:
Title: {title}
Description: {description}
Content: {content}"""

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        log.error(f"Claude error: {e}")
        return None


def generate_image(article_title):
    """Генерирует изображение через Replicate API"""
    try:
        replicate.api_token = REPLICATE_API_KEY
        prompt = f"Professional news illustration about: {article_title}. High quality, clean design."
        output = replicate.run(
            "stability-ai/stable-diffusion-3", input={"prompt": prompt}
        )
        if output:
            return output[0]
    except Exception as e:
        log.error(f"Image generation error: {e}")
    return None


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок одобрения/пропуска и расписания"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("edit_"):
        article_id = data.split("_")[1]
        article = pending_articles.get(article_id)
        if article:
            context.user_data["editing_article_id"] = article_id
            current_text = article.get("text", "")
            await query.edit_message_text(f"Отправьте новый текст:\n\n{current_text}")
        return

    # Одобрить публикацию
    if data.startswith("approve_"):
        article_id = data.split("_")[1]
        article = pending_articles.get(article_id)
        if article:
            url = article.get("url", "")
            post_text = article.get("text", "")
            post_text += f'\n\n📰 Источник: <a href="{url}">Читать полностью</a>'

            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            try:
                image_url = article.get("urlToImage")
                if image_url:
                    try:
                        await bot.send_photo(
                            chat_id=TELEGRAM_CHANNEL,
                            photo=image_url,
                            caption=post_text[:1024],
                            parse_mode="HTML",
                        )
                    except:
                        await bot.send_message(
                            chat_id=TELEGRAM_CHANNEL,
                            text=post_text[:4096],
                            parse_mode="HTML",
                        )
                else:
                    await bot.send_message(
                        chat_id=TELEGRAM_CHANNEL,
                        text=post_text[:4096],
                        parse_mode="HTML",
                    )

                published_urls.add(url)
                await query.edit_message_text("✅ Опубликовано в канал!")
                if article_id in pending_articles:
                    del pending_articles[article_id]
                log.info(f"Published: {article.get('title', '')[:60]}")
            except Exception as e:
                log.error(f"Error publishing: {e}")
                await query.edit_message_text(f"❌ Ошибка: {e}")

    # Пропустить новость
    elif data.startswith("skip_"):
        article_id = data.split("_")[1]
        await query.edit_message_text("⏭️ Пропущено")
        if article_id in pending_articles:
            del pending_articles[article_id]

    # Показать статус расписания
    elif data == "sched_show":
        status = "✅ Включено" if schedule_config["enabled"] else "❌ Отключено"
        times = ", ".join(schedule_config["times"])
        await query.edit_message_text(f"📋 Статус: {status}\n⏰ Время: {times}")

    # Включить расписание
    elif data == "sched_on":
        schedule_config["enabled"] = True
        save_schedule()
        await query.edit_message_text("✅ Расписание включено!")

    # Отключить расписание
    elif data == "sched_off":
        schedule_config["enabled"] = False
        save_schedule()
        await query.edit_message_text("❌ Расписание отключено!")

    # Выбор времени расписания
    elif data == "sched_set":
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
                [
                    InlineKeyboardButton(
                        "10:00, 14:00, 19:00", callback_data="time_alt2"
                    )
                ],
            ]
        )
        await query.edit_message_text("⏰ Выберите расписание:", reply_markup=keyboard)

    # Установить время
    elif data.startswith("time_"):
        preset = data.split("_")[1]
        presets = {
            "default": ["09:00", "13:00", "18:00", "20:00"],
            "alt1": ["08:00", "12:00", "17:00", "21:00"],
            "alt2": ["10:00", "14:00", "19:00"],
        }
        new_times = presets.get(preset, presets["default"])
        schedule_config["times"] = new_times
        schedule_config["enabled"] = True
        save_schedule()
        await query.edit_message_text(
            f"⏰ Расписание установлено:\n{', '.join(new_times)}"
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


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка редактирования текста"""
    article_id = context.user_data.get("editing_article_id")
    if article_id and article_id in pending_articles:
        new_text = update.message.text
        pending_articles[article_id]["text"] = new_text

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Опубликовать", callback_data=f"approve_{article_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Пропустить", callback_data=f"skip_{article_id}"
                    ),
                ]
            ]
        )
        await update.message.reply_text(
            "✏️ Текст обновлён! Опубликовать?", reply_markup=keyboard
        )


async def run_bot(bot: Bot):
    """Основная функция: получает новости, переписывает, отправляет для одобрения"""
    log.info("📰 Проверка новостей...")
    articles = fetch_news()

    if not articles:
        log.info("Новостей не найдено")
        return

    sent_count = 0

    for article in articles:
        if sent_count >= POSTS_PER_RUN:
            break

        url = article.get("url", "")
        if url in published_urls:
            continue

        # Переписываем статью на русский
        log.info(f"🔄 Переписываю: {article.get('title', '')[:60]}...")
        post_text = rewrite_article(article)

        if not post_text:
            log.warning(f"Не удалось переписать статью")
            continue

        # Сохраняем статью с постом
        article_id = str(int(time.time() * 1000000) % 1000000)
        pending_articles[article_id] = {**article, "text": post_text}

        # Создаём кнопки одобрения
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✏️ Редактировать", callback_data=f"edit_{article_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "✅ Опубликовать", callback_data=f"approve_{article_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Пропустить", callback_data=f"skip_{article_id}"
                    ),
                ],
            ]
        )

        # Отправляем готовый пост для одобрения
        try:
            source = article.get("source", {}).get("name", "Unknown")
            message_text = f'{post_text[:900]}\n\n📰 Источник: {source}\n🔗 <a href="{url}">Оригинал</a>'
            image_url = article.get("urlToImage")
            if not image_url:
                image_url = generate_image(article.get("title", ""))

            if image_url:
                await bot.send_photo(
                    chat_id=USER_ID,
                    photo=image_url,
                    caption=message_text,
                    parse_mode="HTML",
                )
                # Отправляем кнопки отдельным сообщением
                await bot.send_message(
                    chat_id=USER_ID,
                    text="Выберите действие:",
                    reply_markup=keyboard,
                )
            else:
                await bot.send_message(
                    chat_id=USER_ID,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            sent_count += 1
            log.info(f"✅ Отправлено для одобрения: {article.get('title', '')[:60]}")
            time.sleep(2)
        except Exception as e:
            log.error(f"Ошибка отправки: {e}")

    log.info(f"✅ Готово! Отправлено {sent_count} новостей для одобрения")


async def main():
    load_schedule()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 Добро пожаловать! Я буду присылать вам новости на одобрение."
        )

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )

    async with app:
        await app.start()
        log.info("🤖 Бот запущен!")

        bot = app.bot

        # Первый запуск при старте
        await run_bot(bot)

        # Настройка расписания через asyncio задачи
        async def scheduler_loop():
            while True:
                if schedule_config["enabled"]:
                    now = time.strftime("%H:%M")
                    if now in schedule_config["times"]:
                        await run_bot(bot)
                        await asyncio.sleep(61)
                await asyncio.sleep(30)

        asyncio.create_task(scheduler_loop())

        if schedule_config["enabled"]:
            log.info(f"📅 Расписание включено: {', '.join(schedule_config['times'])}")
        else:
            log.info("📅 Расписание отключено")

        await app.updater.start_polling()
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
