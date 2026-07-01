import json
from datetime import datetime, timezone

from tracking.db import get_conn


class PendingRepo:
    """Черновики, ожидающие одобрения. Переживает рестарт процесса (в отличие от dict в памяти)."""

    @staticmethod
    def add(item_id, raw_item, text):
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO pending "
                "(id, source_type, source_url, title, text, image_url, raw_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item_id,
                    raw_item.source_type,
                    raw_item.url,
                    raw_item.title,
                    text,
                    raw_item.image_url,
                    json.dumps(raw_item.__dict__, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    @staticmethod
    def get(item_id):
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM pending WHERE id = ?", (item_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_text(item_id, text):
        with get_conn() as conn:
            conn.execute("UPDATE pending SET text = ? WHERE id = ?", (text, item_id))

    @staticmethod
    def delete(item_id):
        with get_conn() as conn:
            conn.execute("DELETE FROM pending WHERE id = ?", (item_id,))


class PublishedRepo:
    """Лог опубликованного — источник дедупликации и трекинга по ТЗ."""

    @staticmethod
    def add(source_type, source_url, channel, title, text, image_url):
        with get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO published "
                "(source_type, source_url, channel, title, text, image_url, published_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    source_type,
                    source_url,
                    channel,
                    title,
                    text,
                    image_url,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    @staticmethod
    def published_urls(channel):
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT source_url FROM published WHERE channel = ?", (channel,)
            ).fetchall()
            return {r["source_url"] for r in rows}
