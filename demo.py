"""End-to-end demo: build a taste profile, then show stats + recommendations.

Run with::

    python demo.py
"""

from __future__ import annotations

from watchlist import WatchlistStore, load_catalog_file
from watchlist.recommender import ContentRecommender


def main() -> None:
    store = WatchlistStore(":memory:")
    n = load_catalog_file(store)
    print(f"Catalog loaded: {n} films.\n")

    # A viewer who loves cerebral sci-fi, with a couple of other watches.
    watched = [
        ("Interstellar", 2014, 9.5),
        ("The Matrix", 1999, 9.0),
        ("Arrival", 2016, 9.0),
        ("Ex Machina", 2014, 8.5),
        ("Whiplash", 2014, 6.0),     # liked, but lukewarm
        ("La La Land", 2016, 4.0),   # not their thing
    ]
    for title, year, rating in watched:
        store.mark_watched(title, year, rating)

    # A few things flagged to watch later (one sci-fi, one not).
    store.add_to_watchlist("Dune", 2021)
    store.add_to_watchlist("Before Sunrise", 1995)

    print("=== Watched ===")
    for e in store.watched():
        print(f"  [{e.rating:>4}] {e.film.title} ({e.film.year}) "
              f"— {', '.join(e.film.genres)}")

    print("\n=== Watchlist (to watch) ===")
    for e in store.to_watch():
        print(f"  {e.film.title} ({e.film.year}) — {', '.join(e.film.genres)}")

    print("\n=== Stats ===")
    s = store.stats()
    print(f"  Watched:       {s['watched_count']}")
    print(f"  To watch:      {s['to_watch_count']}")
    print(f"  Avg rating:    {s['avg_rating']}")
    print(f"  Total runtime: {s['total_runtime']} min "
          f"({s['total_runtime'] / 60:.1f} h)")
    print("  Genre breakdown (watched):")
    for genre, count in s["genre_breakdown"].items():
        print(f"    {genre:<12} {count}")

    print("\n=== Recommendations (content-based) ===")
    rec = ContentRecommender(store)
    for r in rec.recommend(k=6):
        print(f"  {r.score:.3f}  {r.film.title} ({r.film.year}) "
              f"— {', '.join(r.film.genres)}")

    store.close()


if __name__ == "__main__":
    main()
