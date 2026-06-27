"""Data model for the watchlist.

A small, dependency-free set of dataclasses describing films and the
user's relationship to them. The SQLite layer in ``store.py`` maps rows
to and from these objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# A film's status in the user's lists.
UNLISTED = "unlisted"   # known to the catalog, not on any list
TO_WATCH = "to_watch"   # on the watchlist, not yet seen
WATCHED = "watched"     # seen (may carry a rating)

STATUSES = (UNLISTED, TO_WATCH, WATCHED)


@dataclass
class Film:
    """A film in the catalog."""

    title: str
    year: int
    runtime: int                      # minutes
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    id: Optional[int] = None

    def features(self) -> list[str]:
        """Content features used by the recommender (genres + tags)."""
        return [*self.genres, *self.tags]


@dataclass
class Entry:
    """A user's listing of a film (status + optional rating)."""

    film: Film
    status: str = TO_WATCH
    rating: Optional[float] = None    # 0..10, only meaningful when watched

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown status: {self.status!r}")
        if self.rating is not None and not (0.0 <= self.rating <= 10.0):
            raise ValueError("rating must be between 0 and 10")
        if self.rating is not None and self.status != WATCHED:
            raise ValueError("only watched films can carry a rating")
