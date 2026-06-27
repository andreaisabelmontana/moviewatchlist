"""Tests for the SQLite store: CRUD, status transitions, persistence, stats."""

import os
import tempfile

import pytest

from watchlist import WatchlistStore, load_catalog_file
from watchlist.models import TO_WATCH, WATCHED


@pytest.fixture
def store():
    s = WatchlistStore(":memory:")
    s.add_film("The Matrix", 1999, 136, ["Sci-Fi", "Action"], ["dystopia"])
    s.add_film("Whiplash", 2014, 106, ["Drama", "Music"], ["music"])
    s.add_film("Arrival", 2016, 116, ["Sci-Fi", "Drama"], ["aliens"])
    yield s
    s.close()


def test_add_film_idempotent(store):
    f1 = store.add_film("The Matrix", 1999, 136, ["Sci-Fi"])
    # Re-adding the same title+year does not create a duplicate.
    assert len(store.all_films()) == 3
    assert f1.id == store.get_film("The Matrix", 1999).id


def test_add_to_watchlist(store):
    entry = store.add_to_watchlist("Arrival", 2016)
    assert entry.status == TO_WATCH
    assert entry.rating is None
    assert [e.film.title for e in store.to_watch()] == ["Arrival"]


def test_status_transition_to_watch_then_watched(store):
    store.add_to_watchlist("The Matrix", 1999)
    assert store.get_entry("The Matrix", 1999).status == TO_WATCH

    # Transition to watched with a rating.
    store.mark_watched("The Matrix", 1999, rating=9.0)
    entry = store.get_entry("The Matrix", 1999)
    assert entry.status == WATCHED
    assert entry.rating == 9.0

    # It should no longer appear on the to-watch list.
    assert store.to_watch() == []
    assert [e.film.title for e in store.watched()] == ["The Matrix"]


def test_mark_watched_without_prior_listing(store):
    entry = store.mark_watched("Whiplash", 2014, rating=8.5)
    assert entry.status == WATCHED
    assert entry.rating == 8.5


def test_rate_updates_rating(store):
    store.mark_watched("Whiplash", 2014)
    assert store.get_entry("Whiplash", 2014).rating is None
    store.rate("Whiplash", 2014, 7.5)
    assert store.get_entry("Whiplash", 2014).rating == 7.5


def test_rating_bounds_rejected(store):
    with pytest.raises(ValueError):
        store.mark_watched("Whiplash", 2014, rating=11.0)


def test_remove(store):
    store.add_to_watchlist("Arrival", 2016)
    assert store.remove("Arrival", 2016) is True
    assert store.get_entry("Arrival", 2016) is None
    # Removing again returns False; film stays in the catalog.
    assert store.remove("Arrival", 2016) is False
    assert store.get_film("Arrival", 2016) is not None


def test_mark_unknown_film_raises(store):
    with pytest.raises(KeyError):
        store.mark_watched("Nonexistent Film", 2000)


def test_filter_films(store):
    scifi = store.filter_films(genre="Sci-Fi")
    assert {f.title for f in scifi} == {"The Matrix", "Arrival"}
    recent = store.filter_films(min_year=2015)
    assert {f.title for f in recent} == {"Arrival"}


def test_stats_known_set(store):
    # Watched: Matrix(136, 9.0), Whiplash(106, 7.0); to-watch: Arrival.
    store.mark_watched("The Matrix", 1999, 9.0)
    store.mark_watched("Whiplash", 2014, 7.0)
    store.add_to_watchlist("Arrival", 2016)

    s = store.stats()
    assert s["watched_count"] == 2
    assert s["to_watch_count"] == 1
    assert s["avg_rating"] == 8.0                 # (9 + 7) / 2
    assert s["total_runtime"] == 242              # 136 + 106
    # Genre breakdown counts each watched film's genres.
    assert s["genre_breakdown"]["Sci-Fi"] == 1
    assert s["genre_breakdown"]["Action"] == 1
    assert s["genre_breakdown"]["Drama"] == 1
    assert s["genre_breakdown"]["Music"] == 1


def test_avg_rating_ignores_unrated(store):
    store.mark_watched("The Matrix", 1999, 8.0)
    store.mark_watched("Whiplash", 2014)          # no rating
    s = store.stats()
    assert s["watched_count"] == 2
    assert s["rated_count"] == 1
    assert s["avg_rating"] == 8.0                 # only the rated one counts


def test_persistence_across_connections():
    """Data written through one connection is visible after reopening."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        s1 = WatchlistStore(path)
        s1.add_film("Dune", 2021, 155, ["Sci-Fi", "Adventure"], ["desert"])
        s1.mark_watched("Dune", 2021, 8.0)
        s1.close()

        s2 = WatchlistStore(path)
        entry = s2.get_entry("Dune", 2021)
        assert entry is not None
        assert entry.status == WATCHED
        assert entry.rating == 8.0
        s2.close()
    finally:
        os.remove(path)


def test_load_catalog_file():
    s = WatchlistStore(":memory:")
    n = load_catalog_file(s)
    assert n >= 30
    assert len(s.all_films()) == n
    assert s.get_film("Interstellar", 2014) is not None
    s.close()
