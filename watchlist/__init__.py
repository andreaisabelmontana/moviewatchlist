"""watchlist — a SQLite-backed film watchlist + content-based recommender."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Entry, Film, TO_WATCH, WATCHED, UNLISTED
from .recommender import ContentRecommender, Recommendation
from .store import WatchlistStore

__all__ = [
    "Entry",
    "Film",
    "TO_WATCH",
    "WATCHED",
    "UNLISTED",
    "ContentRecommender",
    "Recommendation",
    "WatchlistStore",
    "load_catalog_file",
    "CATALOG_PATH",
]

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


def load_catalog_file(store: WatchlistStore, path: "str | Path | None" = None) -> int:
    """Load the committed JSON catalog into ``store``. Returns film count."""
    path = Path(path) if path else CATALOG_PATH
    films = json.loads(Path(path).read_text(encoding="utf-8"))
    return store.load_catalog(films)
