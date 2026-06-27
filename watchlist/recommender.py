"""Content-based film recommender.

Each film is described by a bag of content features (its genres and
tags). We TF-IDF–vectorise those bags across the whole catalog, then
build a *taste profile* from the films the user has watched, weighted by
how highly they rated each one. Unseen films are ranked by cosine
similarity to that profile.

Why TF-IDF rather than plain one-hot: it down-weights features that
appear in almost every film (so ubiquitous genres don't drown out the
signal) and up-weights the rarer, more discriminating tags.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Film, WATCHED
from .store import WatchlistStore


@dataclass
class Recommendation:
    film: Film
    score: float


# Ratings at/above this count as a positive signal; below, as negative.
# Unrated watched films are treated as mildly positive (the user chose
# to watch them).
NEUTRAL_RATING = 6.0
DEFAULT_WEIGHT = 0.5      # weight for a watched-but-unrated film
TO_WATCH_BONUS = 0.15     # nudge toward films already on the watchlist


class ContentRecommender:
    """Fit on a catalog, then recommend against a user's lists.

    The vectoriser is fit once over every film in the catalog so that
    IDF weights are stable regardless of which films the user has seen.
    """

    def __init__(self, store: WatchlistStore) -> None:
        self.store = store
        self.films: list[Film] = store.all_films()
        if not self.films:
            raise ValueError("cannot fit recommender on an empty catalog")
        self._vectorizer = TfidfVectorizer(
            tokenizer=_identity, preprocessor=_identity, token_pattern=None
        )
        corpus = [f.features() for f in self.films]
        self._matrix = self._vectorizer.fit_transform(corpus)
        self._index = {f.id: i for i, f in enumerate(self.films)}

    def _profile(self) -> Optional[np.ndarray]:
        """Build the weighted taste vector from watched films.

        Each watched film contributes its feature vector scaled by
        ``rating - NEUTRAL_RATING`` (so films rated above the neutral
        point pull the profile toward their content and films rated
        below push away from it). Unrated watched films get a small
        positive default weight.
        """
        watched = self.store.watched()
        if not watched:
            return None
        rows, weights = [], []
        for entry in watched:
            idx = self._index.get(entry.film.id)
            if idx is None:
                continue
            if entry.rating is None:
                weight = DEFAULT_WEIGHT
            else:
                weight = entry.rating - NEUTRAL_RATING
            if weight == 0:
                continue
            rows.append(idx)
            weights.append(weight)
        if not rows:
            return None
        vectors = self._matrix[rows].toarray()
        weighted = vectors * np.array(weights)[:, None]
        profile = weighted.sum(axis=0)
        norm = np.linalg.norm(profile)
        if norm == 0:
            return None
        return profile / norm

    def recommend(
        self, k: int = 5, bias_to_watch: bool = True
    ) -> list[Recommendation]:
        """Return up to ``k`` unseen films ranked by taste similarity.

        Films already on any list (watched or to-watch) are excluded
        from the results. When ``bias_to_watch`` is set, films on the
        to-watch list are *re-included* with a small score bonus so the
        recommender can surface things the user already flagged.
        """
        profile = self._profile()
        if profile is None:
            return []

        sims = cosine_similarity(profile.reshape(1, -1), self._matrix).ravel()
        listed = self.store.listed_film_ids()
        watched_ids = {e.film.id for e in self.store.watched()}
        to_watch_ids = {e.film.id for e in self.store.to_watch()}

        scored: list[Recommendation] = []
        for film, sim in zip(self.films, sims):
            if film.id in watched_ids:
                continue  # never recommend something already seen
            on_watchlist = film.id in to_watch_ids
            if film.id in listed and not on_watchlist:
                continue
            if on_watchlist and not bias_to_watch:
                continue
            score = float(sim)
            if on_watchlist and bias_to_watch:
                score += TO_WATCH_BONUS
            if score <= 0:
                continue
            scored.append(Recommendation(film=film, score=round(score, 4)))

        scored.sort(key=lambda r: (-r.score, r.film.title))
        return scored[:k]


def _identity(x):
    """Pass feature lists straight through the vectoriser unchanged."""
    return x
