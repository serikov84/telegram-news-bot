import sqlite3
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS pending (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    text TEXT NOT NULL,
    image_url TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS published (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_url TEXT,
    channel TEXT NOT NULL,
    title TEXT,
    text TEXT NOT NULL,
    image_url TEXT,
    published_at TEXT NOT NULL,
    UNIQUE(source_url, channel)
);
"""


def init_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
