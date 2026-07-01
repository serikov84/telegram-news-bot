import asyncio
import json
import logging
import time

import config

log = logging.getLogger(__name__)

schedule_config = dict(config.DEFAULT_SCHEDULE)


def load_schedule():
    global schedule_config
    try:
        with open(config.SCHEDULE_PATH, "r") as f:
            schedule_config = json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        log.error(f"Не удалось загрузить расписание: {e}")


def save_schedule():
    try:
        with open(config.SCHEDULE_PATH, "w") as f:
            json.dump(schedule_config, f)
    except Exception as e:
        log.error(f"Не удалось сохранить расписание: {e}")


async def run_loop(run_fn):
    """run_fn: async callable без аргументов, выполняется при наступлении времени из расписания."""
    fired_this_minute = None
    while True:
        if schedule_config["enabled"]:
            now = time.strftime("%H:%M")
            if now in schedule_config["times"] and now != fired_this_minute:
                fired_this_minute = now
                await run_fn()
        await asyncio.sleep(20)
