# Media Agent — Telegram (Фаза 1)

Автономный агент-лидогенератор: собирает материалы из нескольких источников,
адаптирует их через Claude и публикует в Telegram-канал с ручным одобрением.
Первый шаг на пути к мультиканальному агенту (Telegram → LinkedIn → Instagram/X → сайт).

## Тематика канала

Гибрид: широкая рамка «предпринимательство Россия + ЮАР» с узкой экспертной
специализацией AI/IT/налоги/таможня. Настраивается в [`topics.yaml`](topics.yaml)
без правки кода.

## Архитектура

```
источники (NewsAPI, RSS, Telethon, свои кейсы)
        │
        ▼
  processing/rewrite.py  — рерайт/адаптация через Claude
        │
        ▼
  bot/handlers.py  — черновик → апруверу (Edit / Approve / Skip)
        │
        ▼
  publishers/telegram_publisher.py  — публикация в канал
        │
        ▼
  tracking/  (SQLite) — лог опубликованного, дедупликация
```

- `sources/` — каждый источник отдаёт список `RawItem` (общий формат, `sources/base.py`)
  - `newsapi_source.py` — NewsAPI по запросам из `topics.yaml`
  - `rss_source.py` — RSS/Atom ленты из `feeds.yaml`
  - `cases_source.py` — ваши кейсы из `cases/*.md`
  - `telethon_source.py` — парсинг Telegram-каналов (выключено по умолчанию, см. ниже)
- `processing/` — `rewrite.py` (Claude), `image.py` (Replicate, опционально)
- `publishers/telegram_publisher.py` — отправка в канал
- `bot/` — Telegram-бот апрувера: кнопки, редактирование, управление расписанием
- `tracking/` — SQLite (`data/bot.db`): таблицы `pending` (черновики, переживают рестарт)
  и `published` (лог публикаций + дедуп по паре источник+канал)

## Настройка

1. `cp .env.example .env` и заполните переменные:
   - `TELEGRAM_BOT_TOKEN` — токен бота от [@BotFather](https://t.me/BotFather)
   - `TELEGRAM_CHANNEL` — канал для публикации, например `@your_channel` (бот должен быть админом)
   - `USER_ID` — ваш Telegram user id (апрувер), узнать можно у [@userinfobot](https://t.me/userinfobot)
   - `ANTHROPIC_API_KEY` — ключ Anthropic для рерайта
   - `NEWS_API_KEY` — ключ [newsapi.org](https://newsapi.org)
   - `REPLICATE_API_KEY` — опционально, для генерации иллюстраций
2. `pip install -r requirements.txt`
3. `python main.py`

При первом запуске автоматически создаётся `data/` с SQLite-базой и `schedule.json`.
**`data/` должна быть постоянным томом** — если она стирается при каждом деплое,
теряются история публикаций и очередь на одобрение.

## Как добавить RSS-ленту

Добавьте URL в `feeds.yaml`:

```yaml
feeds:
  - url: "https://example.com/rss.xml"
    category: niche   # broad | niche
```

## Как добавить свой кейс

Создайте `cases/мой-кейс.md`:

```markdown
---
title: Заголовок кейса
date: 2026-07-01
category: niche
---

Текст кейса...
```

Пример — `cases/example.md.sample` (переименуйте в `.md`, чтобы он попал в обработку).

## Как настроить тематику

Правьте списки запросов в `topics.yaml` (`broad`/`niche`), количество постов за
запуск (`posts_per_run`) и глубину поиска (`lookback_hours`) — без правки кода.

## Telethon (парсинг Telegram-каналов) — опционально

Требует юзер-сессию Telegram (не бот-токен): `api_id`/`api_hash` с
[my.telegram.org](https://my.telegram.org) и одноразовый интерактивный логин
(ввод номера телефона и кода), который **нельзя выполнить в облачном
контейнере** — только локально, один раз:

```python
from telethon import TelegramClient
client = TelegramClient("data/telethon.session", api_id, api_hash)
client.start()  # запросит номер телефона и код
```

После этого скопируйте `data/telethon.session` туда, где будет работать бот,
и включите источник:

```
TELETHON_ENABLED=true
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELETHON_CHANNELS=@channel1,@channel2
```

Пока сессии нет или `TELETHON_ENABLED=false` — источник просто пропускается,
без ошибок.

## Управление ботом

- `/start` — приветствие
- `/schedule` — включить/отключить автозапуск по расписанию, выбрать время
- Каждый черновик приходит апруверу (`USER_ID`) с кнопками:
  - ✏️ Редактировать — прислать новый текст перед публикацией
  - ✅ Опубликовать — отправить в канал
  - ❌ Пропустить — удалить черновик

## Деплой

`Procfile`: `worker: python main.py` — обычный воркер-процесс, без веб-сервера.

## Дорожная карта (по ТЗ)

1. ✅ **MVP** — Telegram-канал с ручным approve (текущая фаза)
2. Полная автономность на Telegram (без ручного approve)
3. LinkedIn (англоязычный контент)
4. Instagram / X / сайт
