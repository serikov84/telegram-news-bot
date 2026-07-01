from dataclasses import dataclass
from typing import Optional


@dataclass
class RawItem:
    """Общий формат материала независимо от источника (NewsAPI, RSS, Telethon, кейсы)."""

    title: str
    description: str
    content: str
    url: str
    source_type: str
    source_name: str = ""
    image_url: Optional[str] = None
    published_at: Optional[str] = None
    category: str = ""
