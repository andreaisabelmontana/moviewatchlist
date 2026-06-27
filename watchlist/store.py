"""SQLite-backed store for films and the user's lists.

Two tables:

* ``films``   — the catalog (title, year, runtime, genres, tags).
* ``entries`` — one row per film the user has listed, with a status
                (``to_watch`` / ``watched``) and an optional rating.

Genres and tags are stored as JSON arrays in TEXT columns; this keeps
the schema simple and the values queryable enough for our needs.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from typing import Iterable, Iterator, Optional

from .models import Entry, Film, TO_WATCH, WATCHED

_SCHEMA = """
CREATE TABLE IF NOT EXISTS films (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    title   TEXT    NOT NULL,
    year    INTEGER NOT NULL,
    runtime INTEGER NOT NULL,
    genres  TEXT    NOT NULL DEFAULT '[]',
    tags    TEXT    NOT NULL DEFAULT '[]',
    UNIQUE (title, year)
);

CREATE TABLE IF NOT EXISTS entries (
    film_id INTEGER PRIMARY KEY REFERENCES films(id) ON DELETE CASCADE,
    status  TEXT    NOT NULL,
    rating  REAL
);
"""


class WatchlistStore:
    """A SQLite-backed catalog + watchlist.

    Use ``":memory:"`` for an in-process database (handy in tests) or a
    file path to persist between runs.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "WatchlistStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- films -------------------------------------------------------------

    def add_film(
        self,
        title: str,
        year: int,
        runtime: int,
        genres: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> Film:
        """Insert a film into the catalog (idempotent on title+year)."""
        genres = list(genres or [])
        tags = list(tags or [])
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO films (title, year, runtime, genres, tags) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, year, runtime, json.dumps(genres), json.dumps(tags)),
        )
        self.conn.commit()
        if cur.lastrowid and cur.rowcount:
            return Film(title, year, runtime, genres, tags, id=cur.lastrowid)
        # Already present — return the existing row.
        existing = self.get_film(title, year)
        assert existing is not None
        return existing

    def get_film(self, title: str, year: int) -> Optional[Film]:
        row = self.conn.execute(
            "SELECT * FROM films WHERE title = ? AND year = ?", (title, year)
        ).fetchone()
        return _row_to_film(row) if row else None

    def get_film_by_id(self, film_id: int) -> Optional[Film]:
        row = self.conn.execute(
            "SELECT * FROM films WHERE id = ?", (film_id,)
        ).fetchone()
        return _row_to_film(row) if row else None

    def all_films(self) -> list[Film]:
        rows = self.conn.execute("SELECT * FROM films ORDER BY id").fetchall()
        return [_row_to_film(r) for r in rows]

    def load_catalog(self, films: Iterable[dict]) -> int:
        """Bulk-add films from dicts (e.g. parsed from ``catalog.json``)."""
        count = 0
        for f in films:
            self.add_film(
                f["title"], f["year"], f["runtime"],
                f.get("genres"), f.get("tags"),
            )
            count += 1
        return count

    # -- list operations ---------------------------------------------------

    def _require_film_id(self, title: str, year: int) -> int:
        film = self.get_film(title, year)
        if film is None or film.id is None:
            raise KeyError(f"film not in catalog: {title!r} ({year})")
        return film.id

    def add_to_watchlist(self, title: str, year: int) -> Entry:
        """Mark a catalog film as ``to_watch`` (clears any rating)."""
        film_id = self._require_film_id(title, year)
        self.conn.execute(
            "INSERT INTO entries (film_id, status, rating) VALUES (?, ?, NULL) "
            "ON CONFLICT(film_id) DO UPDATE SET status = excluded.status, rating = NULL",
            (film_id, TO_WATCH),
        )
        self.conn.commit()
        return self.get_entry(title, year)  # type: ignore[return-value]

    def mark_watched(
        self, title: str, year: int, rating: Optional[float] = None
    ) -> Entry:
        """Mark a film ``watched``, optionally recording a rating (0..10).

        Works whether or not the film was already on the watchlist, so it
        also drives the ``to_watch -> watched`` transition.
        """
        if rating is not None and not (0.0 <= rating <= 10.0):
            raise ValueError("rating must be between 0 and 10")
        film_id = self._require_film_id(title, year)
        self.conn.execute(
            "INSERT INTO entries (film_id, status, rating) VALUES (?, ?, ?) "
            "ON CONFLICT(film_id) DO UPDATE SET status = excluded.status, "
            "rating = excluded.rating",
            (film_id, WATCHED, rating),
        )
        self.conn.commit()
        return self.get_entry(title, year)  # type: ignore[return-value]

    def rate(self, title: str, year: int, rating: float) -> Entry:
        """Set a rating on a watched film."""
        return self.mark_watched(title, year, rating)

    def remove(self, title: str, year: int) -> bool:
        """Remove a film from the user's lists (keeps it in the catalog)."""
        film_id = self._require_film_id(title, year)
        cur = self.conn.execute(
            "DELETE FROM entries WHERE film_id = ?", (film_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    # -- queries -----------------------------------------------------------

    def get_entry(self, title: str, year: int) -> Optional[Entry]:
        film = self.get_film(title, year)
        if film is None:
            return None
        row = self.conn.execute(
            "SELECT status, rating FROM entries WHERE film_id = ?", (film.id,)
        ).fetchone()
        if row is None:
            return None
        return Entry(film=film, status=row["status"], rating=row["rating"])

    def _entries(self, status: Optional[str] = None) -> Iterator[Entry]:
        sql = (
            "SELECT f.*, e.status AS e_status, e.rating AS e_rating "
            "FROM entries e JOIN films f ON f.id = e.film_id"
        )
        params: tuple = ()
        if status is not None:
            sql += " WHERE e.status = ?"
            params = (status,)
        sql += " ORDER BY f.title"
        for row in self.conn.execute(sql, params).fetchall():
            yield Entry(
                film=_row_to_film(row),
                status=row["e_status"],
                rating=row["e_rating"],
            )

    def watched(self) -> list[Entry]:
        return list(self._entries(WATCHED))

    def to_watch(self) -> list[Entry]:
        return list(self._entries(TO_WATCH))

    def listed_film_ids(self) -> set[int]:
        """IDs of every film on any list (watched or to-watch)."""
        rows = self.conn.execute("SELECT film_id FROM entries").fetchall()
        return {r["film_id"] for r in rows}

    def filter_films(
        self,
        genre: Optional[str] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
    ) -> list[Film]:
        """Filter the catalog by genre and/or year range."""
        films = self.all_films()
        out = []
        for f in films:
            if genre is not None and genre.lower() not in [g.lower() for g in f.genres]:
                continue
            if min_year is not None and f.year < min_year:
                continue
            if max_year is not None and f.year > max_year:
                continue
            out.append(f)
        return out

    # -- stats -------------------------------------------------------------

    def stats(self) -> dict:
        """Summary statistics over the watched list.

        Returns counts, average rating, total watched runtime (minutes),
        and a genre breakdown over watched films.
        """
        watched = self.watched()
        to_watch = self.to_watch()
        ratings = [e.rating for e in watched if e.rating is not None]
        genre_counts: Counter[str] = Counter()
        for e in watched:
            for g in e.film.genres:
                genre_counts[g] += 1
        return {
            "watched_count": len(watched),
            "to_watch_count": len(to_watch),
            "rated_count": len(ratings),
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "total_runtime": sum(e.film.runtime for e in watched),
            "genre_breakdown": dict(genre_counts.most_common()),
        }


def _row_to_film(row: sqlite3.Row) -> Film:
    return Film(
        title=row["title"],
        year=row["year"],
        runtime=row["runtime"],
        genres=json.loads(row["genres"]),
        tags=json.loads(row["tags"]),
        id=row["id"],
    )
