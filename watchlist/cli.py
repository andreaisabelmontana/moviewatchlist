"""Command-line interface for the watchlist.

Usage examples::

    python -m watchlist.cli --db films.db init
    python -m watchlist.cli --db films.db watch "The Matrix" 1999 --rating 9
    python -m watchlist.cli --db films.db towatch "Dune" 2021
    python -m watchlist.cli --db films.db list --status watched
    python -m watchlist.cli --db films.db stats
    python -m watchlist.cli --db films.db recommend -k 5
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from . import load_catalog_file
from .models import WATCHED
from .recommender import ContentRecommender
from .store import WatchlistStore


def _open(db: str) -> WatchlistStore:
    return WatchlistStore(db)


def cmd_init(store: WatchlistStore, args: argparse.Namespace) -> int:
    n = load_catalog_file(store, args.catalog)
    print(f"Loaded {n} films into catalog ({store_films(store)} now present).")
    return 0


def store_films(store: WatchlistStore) -> int:
    return len(store.all_films())


def cmd_catalog(store: WatchlistStore, args: argparse.Namespace) -> int:
    films = store.filter_films(
        genre=args.genre, min_year=args.min_year, max_year=args.max_year
    )
    if not films:
        print("No films match.")
        return 0
    for f in films:
        print(f"{f.title} ({f.year}) — {', '.join(f.genres)} · {f.runtime} min")
    print(f"\n{len(films)} film(s).")
    return 0


def cmd_towatch(store: WatchlistStore, args: argparse.Namespace) -> int:
    entry = store.add_to_watchlist(args.title, args.year)
    print(f"Added to watchlist: {entry.film.title} ({entry.film.year}).")
    return 0


def cmd_watch(store: WatchlistStore, args: argparse.Namespace) -> int:
    entry = store.mark_watched(args.title, args.year, args.rating)
    rating = f" — rated {entry.rating}" if entry.rating is not None else ""
    print(f"Marked watched: {entry.film.title} ({entry.film.year}){rating}.")
    return 0


def cmd_rate(store: WatchlistStore, args: argparse.Namespace) -> int:
    entry = store.rate(args.title, args.year, args.rating)
    print(f"Rated {entry.film.title} ({entry.film.year}): {entry.rating}.")
    return 0


def cmd_remove(store: WatchlistStore, args: argparse.Namespace) -> int:
    ok = store.remove(args.title, args.year)
    print("Removed." if ok else "Not on any list.")
    return 0 if ok else 1


def cmd_list(store: WatchlistStore, args: argparse.Namespace) -> int:
    if args.status == "watched":
        entries = store.watched()
    elif args.status == "to_watch":
        entries = store.to_watch()
    else:
        entries = store.watched() + store.to_watch()
    if not entries:
        print("Nothing listed.")
        return 0
    for e in entries:
        tag = "✓" if e.status == WATCHED else "○"
        rating = f" [{e.rating}]" if e.rating is not None else ""
        print(f"{tag} {e.film.title} ({e.film.year}){rating} — {', '.join(e.film.genres)}")
    return 0


def cmd_stats(store: WatchlistStore, args: argparse.Namespace) -> int:
    s = store.stats()
    print(f"Watched:        {s['watched_count']}")
    print(f"To watch:       {s['to_watch_count']}")
    print(f"Avg rating:     {s['avg_rating']}")
    print(f"Total runtime:  {s['total_runtime']} min "
          f"({s['total_runtime'] / 60:.1f} h watched)")
    if s["genre_breakdown"]:
        print("Genre breakdown (watched):")
        for genre, count in s["genre_breakdown"].items():
            print(f"  {genre:<12} {count}")
    return 0


def cmd_recommend(store: WatchlistStore, args: argparse.Namespace) -> int:
    rec = ContentRecommender(store)
    results = rec.recommend(k=args.k, bias_to_watch=not args.no_bias)
    if not results:
        print("No recommendations yet — mark some films watched first.")
        return 0
    print("Recommended for you:")
    for r in results:
        print(f"  {r.score:.3f}  {r.film.title} ({r.film.year}) "
              f"— {', '.join(r.film.genres)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="watchlist",
        description="Track watched / to-watch films and get content-based recommendations.",
    )
    p.add_argument("--db", default="watchlist.db",
                   help="SQLite database path (default: watchlist.db)")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("init", help="load the committed film catalog")
    pi.add_argument("--catalog", default=None, help="path to a catalog JSON file")
    pi.set_defaults(func=cmd_init)

    pc = sub.add_parser("catalog", help="browse / filter the catalog")
    pc.add_argument("--genre")
    pc.add_argument("--min-year", type=int)
    pc.add_argument("--max-year", type=int)
    pc.set_defaults(func=cmd_catalog)

    pt = sub.add_parser("towatch", help="add a film to the watchlist")
    pt.add_argument("title")
    pt.add_argument("year", type=int)
    pt.set_defaults(func=cmd_towatch)

    pw = sub.add_parser("watch", help="mark a film watched (optionally rate it)")
    pw.add_argument("title")
    pw.add_argument("year", type=int)
    pw.add_argument("--rating", type=float, default=None)
    pw.set_defaults(func=cmd_watch)

    pr = sub.add_parser("rate", help="rate a watched film")
    pr.add_argument("title")
    pr.add_argument("year", type=int)
    pr.add_argument("rating", type=float)
    pr.set_defaults(func=cmd_rate)

    prm = sub.add_parser("remove", help="remove a film from your lists")
    prm.add_argument("title")
    prm.add_argument("year", type=int)
    prm.set_defaults(func=cmd_remove)

    pl = sub.add_parser("list", help="list your films")
    pl.add_argument("--status", choices=["watched", "to_watch", "all"], default="all")
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("stats", help="show viewing statistics")
    ps.set_defaults(func=cmd_stats)

    prc = sub.add_parser("recommend", help="recommend unseen films")
    prc.add_argument("-k", type=int, default=5, help="number of recommendations")
    prc.add_argument("--no-bias", action="store_true",
                     help="do not bias toward the to-watch list")
    prc.set_defaults(func=cmd_recommend)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    store = _open(args.db)
    try:
        return args.func(store, args)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
