"""Tests for the content-based recommender."""

import pytest

from watchlist import WatchlistStore, load_catalog_file
from watchlist.recommender import ContentRecommender


@pytest.fixture
def full_store():
    s = WatchlistStore(":memory:")
    load_catalog_file(s)
    yield s
    s.close()


def test_empty_profile_returns_no_recs(full_store):
    rec = ContentRecommender(full_store)
    assert rec.recommend() == []


def test_scifi_taste_yields_scifi_recs(full_store):
    # Rate three sci-fi films highly; nothing else.
    full_store.mark_watched("Interstellar", 2014, 9.5)
    full_store.mark_watched("The Matrix", 1999, 9.0)
    full_store.mark_watched("Arrival", 2016, 9.0)

    rec = ContentRecommender(full_store)
    results = rec.recommend(k=5)
    assert results, "expected some recommendations"

    titles = [r.film.title for r in results]
    genres_top = full_store.get_film(titles[0], _year_of(full_store, titles[0])).genres
    assert "Sci-Fi" in genres_top

    # The top recommendation should be a sci-fi film.
    rec_genres = [g for r in results for g in r.film.genres]
    assert rec_genres.count("Sci-Fi") >= 3

    # A clearly unrelated film (a period romance) must not top the list.
    assert "Pride and Prejudice" not in titles[:3]
    assert "Before Sunrise" not in titles[:3]


def test_already_watched_is_excluded(full_store):
    full_store.mark_watched("Interstellar", 2014, 9.5)
    full_store.mark_watched("The Matrix", 1999, 9.0)
    full_store.mark_watched("Dune", 2021, 9.0)

    rec = ContentRecommender(full_store)
    results = rec.recommend(k=10)
    titles = {r.film.title for r in results}
    assert "Interstellar" not in titles
    assert "The Matrix" not in titles
    assert "Dune" not in titles


def test_low_rating_pushes_away_from_genre(full_store):
    # Like animation, dislike sci-fi: the disliked genre should be
    # suppressed and the liked one should surface near the top.
    full_store.mark_watched("Spirited Away", 2001, 9.0)
    full_store.mark_watched("Your Name", 2016, 9.0)
    full_store.mark_watched("The Matrix", 1999, 2.0)   # disliked sci-fi

    rec = ContentRecommender(full_store)
    results = rec.recommend(k=8)
    top_titles = [r.film.title for r in results[:5]]

    # No sci-fi film should be recommended — the negative rating cancels
    # the genre's pull.
    for r in results:
        assert "Sci-Fi" not in r.film.genres, r.film.title

    # Animation films (the liked genre) should appear near the top.
    animation_in_top = [
        t for t in top_titles
        if "Animation" in full_store.get_film(t, _year_of(full_store, t)).genres
    ]
    assert animation_in_top, top_titles


def test_to_watch_bias_surfaces_watchlist_item(full_store):
    full_store.mark_watched("Interstellar", 2014, 9.0)
    full_store.mark_watched("Arrival", 2016, 9.0)
    # Put a sci-fi film on the watchlist.
    full_store.add_to_watchlist("Blade Runner 2049", 2017)

    rec = ContentRecommender(full_store)

    biased = {r.film.title for r in rec.recommend(k=10, bias_to_watch=True)}
    assert "Blade Runner 2049" in biased

    unbiased = {r.film.title for r in rec.recommend(k=10, bias_to_watch=False)}
    assert "Blade Runner 2049" not in unbiased


def test_thriller_taste_yields_thriller_recs(full_store):
    full_store.mark_watched("Se7en", 1995, 9.0)
    full_store.mark_watched("Zodiac", 2007, 9.0)
    full_store.mark_watched("Prisoners", 2013, 8.5)

    rec = ContentRecommender(full_store)
    results = rec.recommend(k=5)
    rec_genres = [g for r in results for g in r.film.genres]
    # Thriller/Mystery/Crime should dominate.
    assert (rec_genres.count("Thriller")
            + rec_genres.count("Mystery")
            + rec_genres.count("Crime")) >= 3


def test_scores_are_sorted_descending(full_store):
    full_store.mark_watched("The Matrix", 1999, 9.0)
    full_store.mark_watched("Interstellar", 2014, 9.0)
    rec = ContentRecommender(full_store)
    results = rec.recommend(k=5)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def _year_of(store, title):
    for f in store.all_films():
        if f.title == title:
            return f.year
    raise KeyError(title)
