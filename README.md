# Media Agent — Telegram (Фаза 2)

Автономный агент-лидогенератор: собирает материалы из нескольких источников,
адаптирует их через Claude и публикует в Telegram-канал **автоматически**,
без ручного одобрения — с теневым уведомлением и возможностью отменить пост
после публикации. Первый шаг на пути к мультиканальному агенту
(Telegram → LinkedIn → Instagram/X → сайт).

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
  publishers/telegram_publisher.py  — публикация в канал (сразу, без approve)
        │
        ▼
  bot/handlers.py  — лог в tracking + теневое уведомление апруверу с кнопкой 🗑️
        │
        ▼
  tracking/  (SQLite) — лог опубликованного, дедупликация, дневной лимит
```

- `sources/` — каждый источник отдаёт список `RawItem` (общий формат, `sources/base.py`)
  - `newsapi_source.py` — NewsAPI по запросам из `topics.yaml`
  - `rss_source.py` — RSS/Atom ленты из `feeds.yaml`
  - `cases_source.py` — ваши кейсы из `cases/*.md`
  - `telethon_source.py` — парсинг Telegram-каналов (выключено по умолчанию, см. ниже)
- `processing/` — `rewrite.py` (Claude), `image.py` (Replicate, опционально)
- `publishers/telegram_publisher.py` — отправка в канал
- `bot/` — публикация+уведомление (`publish_and_notify`), кнопка отмены поста, управление расписанием
- `tracking/` — SQLite (`data/bot.db`): таблица `published` — лог публикаций (источник, канал,
  текст, id сообщения в канале, время, отметка об удалении), дедуп и дневной лимит строятся на ней

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
теряются лог публикаций и дедупликация (агент может начать постить уже публиковавшееся).

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
запуск (`posts_per_run`), глубину поиска (`lookback_hours`) и дневной лимит
автопубликаций (`daily_publish_limit`) — без правки кода.

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

## LinkedIn (Фаза 3, в подготовке)

Приложение в LinkedIn Developer Portal создано, продукты одобрены. Осталось
получить access/refresh-токены — это делается **локально, на своей машине**
(нужен логин в браузере, в облачной сессии это невозможно):

1. На вкладке **Auth** приложения возьмите `Client ID`/`Client Secret`, впишите
   в `.env` (`LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`), и добавьте туда же
   Redirect URL `http://localhost:8080/callback` — один в один, включая порт
2. Токен для личного профиля:
   ```
   python scripts/linkedin_auth.py --scope "openid profile email w_member_social"
   ```
3. Токен для страницы компании **aiu** (тот же логин, если вы админ страницы):
   ```
   python scripts/linkedin_auth.py --scope "w_organization_social rw_organization_admin"
   ```
   Точные названия scope сверьте с тем, что показывает вкладка Auth для ваших
   одобренных продуктов — они могут отличаться от примера.
4. Скопируйте `access_token`/`refresh_token` из вывода скрипта в `.env`
   (`LINKEDIN_PERSONAL_*` / `LINKEDIN_COMPANY_*`)
5. Узнайте Organization URN страницы aiu (нужен для публикации от её имени) —
   он виден в адресной строке в админке страницы, либо запросом с токеном
   страницы:
   ```
   curl -H "Authorization: Bearer $LINKEDIN_COMPANY_ACCESS_TOKEN" \
        -H "LinkedIn-Version: 202405" \
        -H "X-Restli-Protocol-Version: 2.0.0" \
        "https://api.linkedin.com/rest/organizationAcls?q=roleAssignee&role=ADMINISTRATOR&state=APPROVED"
   ```
   Сохраните как `LINKEDIN_ORGANIZATION_URN`.

После заполнения `.env` — публишер `publishers/linkedin_publisher.py` и разделение
контента по тону (личный — экспертиза/Sport Hub, aiu — IT-новости) ещё предстоит
реализовать.

## Управление ботом

- `/start` — приветствие
- `/schedule` — включить/отключить автозапуск по расписанию, выбрать время
- Публикация полностью автоматическая: пайплайн сам рерайтит и постит в канал
  (с учётом `posts_per_run` и `daily_publish_limit`)
- После каждой публикации апруверу (`USER_ID`) приходит копия поста с кнопкой
  🗑️ **Удалить из канала** — страховка на случай неудачного текста, работает
  постфактум (пост уже опубликован к этому моменту)

## Деплой

`Procfile`: `worker: python main.py` — обычный воркер-процесс, без веб-сервера.

## Дорожная карта (по ТЗ)

1. ✅ **MVP** — Telegram-канал с ручным approve
2. ✅ **Полная автономность на Telegram** (текущая фаза) — без ручного approve,
   с теневым уведомлением и отменой поста постфактум
3. LinkedIn — два аккаунта: личный профиль (экспертиза, проект Sport Hub) и
   страница компании aiu (IT-новости, как в Telegram-канале). Требует
   одобренного LinkedIn Developer App (`w_member_social` + доступ к
   Community Management/Marketing API для страницы) — заявка ещё не подана,
   это отдельный шаг вне кода перед началом реализации
4. Instagram / X / сайт
