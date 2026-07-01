from datetime import datetime, timezone

from tracking.db import get_conn


class PublishedRepo:
    """Лог опубликованного — источник дедупликации, дневного лимита и трекинга по ТЗ."""

    @staticmethod
    def add(source_type, source_url, channel, title, text, image_url, channel_message_id):
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO published "
                "(source_type, source_url, channel, title, text, image_url, channel_message_id, published_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source_type,
                    source_url,
                    channel,
                    title,
                    text,
                    image_url,
                    channel_message_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return cur.lastrowid

    @staticmethod
    def get(publish_id):
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM published WHERE id = ?", (publish_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def mark_deleted(publish_id):
        with get_conn() as conn:
            conn.execute(
                "UPDATE published SET deleted_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), publish_id),
            )

    @staticmethod
    def published_urls(channel):
        """Все когда-либо опубликованные (включая удалённые вручную) — не пересматриваем их повторно."""
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT source_url FROM published WHERE channel = ?", (channel,)
            ).fetchall()
            return {r["source_url"] for r in rows}

    @staticmethod
    def count_since(channel, since_iso):
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM published "
                "WHERE channel = ? AND published_at >= ? AND deleted_at IS NULL",
                (channel, since_iso),
            ).fetchone()
            return row["c"]
