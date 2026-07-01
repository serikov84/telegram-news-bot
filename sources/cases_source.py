import glob
import logging
import os

import config
from sources.base import RawItem

log = logging.getLogger(__name__)


def fetch():
    items = []
    pattern = os.path.join(config.CASES_DIR, "*.md")
    for path in sorted(glob.glob(pattern)):
        try:
            meta, body = _parse_case_file(path)
            filename = os.path.basename(path)
            items.append(
                RawItem(
                    title=meta.get("title", filename),
                    description=body,
                    content=body,
                    url=f"cases://{filename}",
                    source_type="cases",
                    source_name="Свои кейсы",
                    image_url=None,
                    published_at=meta.get("date"),
                    category=meta.get("category", "niche"),
                )
            )
        except Exception as e:
            log.error(f"Ошибка чтения кейса '{path}': {e}")

    return items


def _parse_case_file(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    meta = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            front, body = parts[1], parts[2].strip()
            for line in front.strip().splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    meta[key.strip()] = value.strip()

    return meta, body
