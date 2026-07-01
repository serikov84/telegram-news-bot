import logging
from datetime import datetime, timedelta

import requests

import config
from sources.base import RawItem

log = logging.getLogger(__name__)


def fetch():
    items = []
    since = (datetime.utcnow() - timedelta(hours=config.NEWS_LOOKBACK_HOURS)).strftime(
        "%Y-%m-%d"
    )
    queries = [(q, "broad") for q in config.BROAD_QUERIES] + [
        (q, "niche") for q in config.NICHE_QUERIES
    ]

    for query, category in queries:
        try:
            r = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "from": since,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": 5,
                    "apiKey": config.NEWS_API_KEY,
                },
                timeout=10,
            )
            data = r.json()
            for a in data.get("articles", []):
                url = a.get("url")
                if not url:
                    continue
                items.append(
                    RawItem(
                        title=a.get("title", "") or "",
                        description=a.get("description", "") or "",
                        content=a.get("content", "") or "",
                        url=url,
                        source_type="newsapi",
                        source_name=(a.get("source") or {}).get("name", "Unknown"),
                        image_url=a.get("urlToImage"),
                        published_at=a.get("publishedAt"),
                        category=category,
                    )
                )
        except Exception as e:
            log.error(f"NewsAPI error for query '{query}': {e}")

    seen = set()
    unique = []
    for item in items:
        if item.url not in seen:
            seen.add(item.url)
            unique.append(item)
    return unique
