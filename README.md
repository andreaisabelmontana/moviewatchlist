# MovieWatchlist

Track the films you've watched and want to watch, and get **content-based
recommendations** from your taste. A small SQLite-backed Python library with a
CLI, a committed film catalog, and a content-based recommender built on
scikit-learn TF-IDF + cosine similarity.

🔗 **Showcase page:** https://andreaisabelmontana.github.io/moviewatchlist/
(The page runs an in-browser illustration of the recommender over the committed
catalog; the real engine described below is Python.)

## Install

```bash
pip install -r requirements.txt
```

Requires Python 3.10+. Dependencies: `numpy`, `scikit-learn` (and `pytest` for tests).

## Data model

Everything lives in one SQLite database with two tables:

| table     | columns                                              |
|-----------|------------------------------------------------------|
| `films`   | `id, title, year, runtime, genres, tags`             |
| `entries` | `film_id, status, rating`                            |

* `films` is the **catalog**. `genres` and `tags` are stored as JSON arrays.
  Films are unique on `(title, year)`.
* `entries` is the user's **lists**: one row per listed film with a
  `status` of `to_watch` or `watched`, plus an optional `rating` (0–10,
  only meaningful when watched).

The `to_watch → watched` transition is just an update to the `status`
(and, optionally, the `rating`) on the entry row. A film always stays in
the catalog even after it's removed from your lists.

Core operations (`watchlist/store.py`):

```python
from watchlist import WatchlistStore, load_catalog_file

store = WatchlistStore("films.db")    # or ":memory:"
load_catalog_file(store)              # load data/catalog.json (34 films)

store.add_to_watchlist("Dune", 2021)
store.mark_watched("The Matrix", 1999, rating=9.0)   # to_watch -> watched
store.rate("The Matrix", 1999, 9.5)

store.watched()        # list[Entry]
store.to_watch()       # list[Entry]
store.filter_films(genre="Sci-Fi", min_year=2010)
store.stats()          # counts, avg rating, total runtime, genre breakdown
```

## The recommender

`watchlist/recommender.py` is **content-based**:

1. Each film is described by a bag of content features — its **genres + tags**.
2. A `TfidfVectorizer` is fit over the whole catalog, so common genres are
   down-weighted and rarer, more discriminating tags are up-weighted (IDF).
3. A **taste profile** is built from your *watched* films, each one weighted
   by `rating − 6.0`. Films rated above the neutral point (6) pull the profile
   toward their content; films rated below it push away. Watched-but-unrated
   films contribute a small positive weight.
4. Unseen films are ranked by **cosine similarity** to the profile.
   Already-watched films are always excluded. By default the recommender also
   gives a small bonus to films already on your to-watch list so it can surface
   things you've already flagged (toggle with `bias_to_watch`).

```python
from watchlist.recommender import ContentRecommender
ContentRecommender(store).recommend(k=5)   # list[Recommendation(film, score)]
```

## CLI

```bash
python -m watchlist.cli --db films.db init                       # load catalog
python -m watchlist.cli --db films.db watch "The Matrix" 1999 --rating 9
python -m watchlist.cli --db films.db towatch "Dune" 2021
python -m watchlist.cli --db films.db list --status watched
python -m watchlist.cli --db films.db stats
python -m watchlist.cli --db films.db recommend -k 5
```

## Example

`python demo.py` seeds a viewer who rates cerebral sci-fi highly (Interstellar
9.5, The Matrix 9.0, Arrival 9.0, Ex Machina 8.5), lukewarm on Whiplash (6.0),
and disliked La La Land (4.0), with Dune and Before Sunrise on the watchlist:

```
=== Stats ===
  Watched:       6
  To watch:      2
  Avg rating:    7.67
  Total runtime: 763 min (12.7 h)
  Genre breakdown (watched):
    Drama        5
    Sci-Fi       4
    Music        2
    Mystery      1
    Thriller     1
    Adventure    1
    Romance      1
    Action       1

=== Recommendations (content-based) ===
  0.416  Dune (2021) — Sci-Fi, Adventure
  0.382  Edge of Tomorrow (2014) — Sci-Fi, Action
  0.369  Blade Runner 2049 (2017) — Sci-Fi, Drama, Mystery
  0.340  Gravity (2013) — Sci-Fi, Thriller, Drama
  0.282  Mad Max: Fury Road (2015) — Action, Adventure, Sci-Fi
  0.146  Skyfall (2012) — Action, Adventure, Thriller
```

The profile leans hard sci-fi, so the top picks are all sci-fi; Dune (on the
watchlist) is surfaced first thanks to the to-watch bias, and the music/romance
films the viewer disliked are pushed down the list.

## Tests

```bash
pip install pytest scikit-learn numpy pandas
python -m pytest -q
```

```
....................                                                     [100%]
20 passed in 3.01s
```

Tests cover CRUD and the `to_watch → watched` rating transition, persistence
across reopened connections, stats on a known set (genre counts, avg rating,
total runtime), and the recommender (a sci-fi taste yields sci-fi recs, a
disliked genre is suppressed, already-watched films are excluded, and the
to-watch bias surfaces flagged films).

## Layout

```
watchlist/
  models.py        Film / Entry dataclasses + status constants
  store.py         SQLite catalog + lists, CRUD, stats
  recommender.py   TF-IDF content-based recommender
  cli.py           argparse CLI
data/catalog.json  34-film seed catalog
tests/             pytest suite
demo.py            end-to-end demo
index.html         static showcase page
```

## License

MIT — see [LICENSE](LICENSE).
