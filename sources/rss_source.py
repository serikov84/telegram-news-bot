import logging
import time
from datetime import datetime, timedelta, timezone

import feedparser

import config
from sources.base import RawItem

log = logging.getLogger(__name__)


def fetch():
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.NEWS_LOOKBACK_HOURS)

    for feed_cfg in config.RSS_FEEDS:
        url = feed_cfg.get("url") if isinstance(feed_cfg, dict) else feed_cfg
        category = feed_cfg.get("category", "broad") if isinstance(feed_cfg, dict) else "broad"
        if not url:
            continue
        try:
            parsed = feedparser.parse(url)
            feed_name = parsed.feed.get("title", url)
            for entry in parsed.entries:
                published = _entry_datetime(entry)
                if published and published < cutoff:
                    continue
                link = entry.get("link")
                if not link:
                    continue
                items.append(
                    RawItem(
                        title=entry.get("title", "") or "",
                        description=entry.get("summary", "") or "",
                        content=entry.get("summary", "") or "",
                        url=link,
                        source_type="rss",
                        source_name=feed_name,
                        image_url=_entry_image(entry),
                        published_at=published.isoformat() if published else None,
                        category=category,
                    )
                )
        except Exception as e:
            log.error(f"RSS error for feed '{url}': {e}")

    return items


def _entry_datetime(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)


def _entry_image(entry):
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media:
        return media[0].get("url")
    for link in entry.get("links", []):
        if str(link.get("type", "")).startswith("image/"):
            return link.get("href")
    return None
