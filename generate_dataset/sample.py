"""
Sampling helper for examining peer-weighted torrent selection characteristics.

The script initialises the shared Peewee models (see `models.py`) against
`test.sqlite` in read-only mode, filters for the video-focused categories, and
surfaces a small sample where items with more peers (`seeders + leechers`) are
favoured. Weighting parameters are derived from the empirical peer distribution
stored in `/tmp/test/peer_stats.json`, allowing quick iteration on sampling
strategy.

By default, torrents without file listings are excluded from sampling. The script
supports filtering by content type (TV shows only with `--tv`, movies only with
`--movie`) or sampling with a specific ratio between TV and movies using
`--split-tv-film`. For each sampled torrent we print the basic metadata, IMDB
identifier (if present), and a summary of every referenced file (path plus size)
so that downstream parsing heuristics can be calibrated interactively.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict

from peewee import fn

from models import (
    File,
    Torrent,
    init_sqlite_database,
)


VIDEO_CATEGORY_IDS = (
    200,  # Video (general)
    201,  # Video: Movies
    202,  # Video: Movies DVDR
    204,  # Video: Movie clips
    205,  # Video: TV shows
    207,  # Video: HD - Movies
    208,  # Video: HD - TV shows
    209,  # Video: 3D
)

MOVIE_CATEGORY_IDS = (
    201,  # Video: Movies
    202,  # Video: Movies DVDR
    207,  # Video: HD - Movies
)

TV_CATEGORY_IDS = (
    205,  # Video: TV shows
    208,  # Video: HD - TV shows
)

database = init_sqlite_database(read_only=True)
PEER_STATS_PATH = Path("/tmp/test/peer_stats.json")


def load_peer_thresholds(path: Path) -> Dict[str, int]:
    default_thresholds = {"p75": 1, "p90": 4, "p95": 14, "p99": 80}
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return default_thresholds
    except json.JSONDecodeError:
        return default_thresholds

    percentiles = data.get("percentiles") or {}
    thresholds = {
        key: max(int(percentiles.get(key, default)), 0)
        for key, default in default_thresholds.items()
    }
    # Ensure strictly increasing ladder to avoid redundant comparisons.
    previous = 0
    for key in ("p75", "p90", "p95", "p99"):
        thresholds[key] = max(thresholds[key], previous)
        previous = thresholds[key]
    return thresholds


PEER_THRESHOLDS = load_peer_thresholds(PEER_STATS_PATH)


def parse_ratio(ratio_str: str) -> tuple[float, float]:
    """
    Parse a ratio string like '0.6:0.4' or '4:3' and return normalized values.

    Parameters
    ----------
    ratio_str:
        String representation of a ratio (e.g., '0.6:0.4', '4:3', '60:40').

    Returns
    -------
    tuple[float, float]:
        Normalized (TV ratio, movie ratio) summing to 1.0.

    Raises
    ------
    ValueError:
        If the ratio string is invalid or contains non-positive values.
    """
    parts = ratio_str.split(":")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid ratio format '{ratio_str}'. Expected format: 'X:Y' (e.g., '0.6:0.4' or '4:3')."
        )

    try:
        tv_part = float(parts[0])
        movie_part = float(parts[1])
    except ValueError as exc:
        raise ValueError(
            f"Invalid ratio values in '{ratio_str}'. Both parts must be numeric."
        ) from exc

    if tv_part <= 0 or movie_part <= 0:
        raise ValueError(
            f"Invalid ratio '{ratio_str}'. Both parts must be positive numbers."
        )

    total = tv_part + movie_part
    return tv_part / total, movie_part / total


def compute_sample_id(sample: dict) -> str:
    """
    Compute a SHA256 hash of the sample object as a unique identifier.

    Parameters
    ----------
    sample:
        Sample dictionary (without sample_id field).

    Returns
    -------
    str:
        First 16 characters of the hexadecimal SHA256 hash of the
        deterministically-sorted JSON.
    """
    # Create deterministic JSON with sorted keys and no whitespace
    json_str = json.dumps(sample, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()[:16]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sample torrents from the video categories with weighting toward "
            "higher peer counts."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of torrents to display (default: 10).",
    )
    parser.add_argument(
        "--include-category",
        action="append",
        type=int,
        help=(
            "Additional category IDs to include. Can be supplied multiple "
            "times."
        ),
    )

    # Mutually exclusive group for content type selection
    content_group = parser.add_mutually_exclusive_group()
    content_group.add_argument(
        "--tv",
        action="store_true",
        help="Include only TV show torrents.",
    )
    content_group.add_argument(
        "--movie",
        action="store_true",
        help="Include only movie torrents.",
    )
    content_group.add_argument(
        "--split-tv-film",
        type=str,
        metavar="RATIO",
        help=(
            "Sample with a ratio of TV to film torrents (e.g., '0.6:0.4' or '4:3'). "
            "Values are normalized, so '4:3' means 4 parts TV to 3 parts movies."
        ),
    )

    parser.add_argument(
        "--include-fileless",
        action="store_true",
        help="Include torrents without file listings (default: exclude them).",
    )

    parser.add_argument(
        "--sample-id",
        action="store_true",
        help="Include a sample_id field (SHA256 hash of deterministically-sorted JSON).",
    )

    return parser.parse_args()


def sample_torrents(
    limit: int,
    include_category: tuple[int, ...],
    *,
    tv_only: bool = False,
    movie_only: bool = False,
    split_ratio: tuple[float, float] | None = None,
    include_fileless: bool = False,
    include_sample_id: bool = False,
) -> list[dict]:
    """
    Sample torrents with peer-weighted random selection.

    Parameters
    ----------
    limit:
        Total number of torrents to sample.
    include_category:
        Additional category IDs to include beyond the default selection.
    tv_only:
        If True, sample only TV show torrents.
    movie_only:
        If True, sample only movie torrents.
    split_ratio:
        If provided, sample TV and movie torrents separately with the given
        (TV ratio, movie ratio) tuple. For example, (0.6, 0.4) means 60% TV
        and 40% movies.
    include_fileless:
        If True, include torrents without file listings. Default is False.
    include_sample_id:
        If True, add a sample_id field (SHA256 hash) to each sample.

    Returns
    -------
    list[dict]:
        List of sampled torrent records with metadata and file information.
    """
    if split_ratio is not None:
        # Sample TV and movies separately with the specified ratio
        tv_ratio, movie_ratio = split_ratio
        tv_limit = int(limit * tv_ratio)
        movie_limit = limit - tv_limit  # Ensure we reach the exact limit

        tv_results = _sample_from_categories(
            TV_CATEGORY_IDS, tv_limit, include_category, include_fileless, include_sample_id
        )
        movie_results = _sample_from_categories(
            MOVIE_CATEGORY_IDS, movie_limit, include_category, include_fileless, include_sample_id
        )

        return tv_results + movie_results

    # Determine which categories to use
    if tv_only:
        categories = TV_CATEGORY_IDS + include_category
    elif movie_only:
        categories = MOVIE_CATEGORY_IDS + include_category
    else:
        categories = VIDEO_CATEGORY_IDS + include_category

    return _sample_from_categories(categories, limit, (), include_fileless, include_sample_id)


def _sample_from_categories(
    base_categories: tuple[int, ...],
    limit: int,
    extra_categories: tuple[int, ...],
    include_fileless: bool,
    include_sample_id: bool,
) -> list[dict]:
    """
    Sample torrents from specified categories with peer weighting.

    Parameters
    ----------
    base_categories:
        Base category IDs to sample from.
    limit:
        Number of torrents to sample.
    extra_categories:
        Additional category IDs to include.
    include_fileless:
        If True, include torrents without file listings.
    include_sample_id:
        If True, add a sample_id field (SHA256 hash) to each sample.

    Returns
    -------
    list[dict]:
        List of sampled torrent records.
    """
    peer_total = Torrent.seeders + Torrent.leechers
    thresholds = PEER_THRESHOLDS
    boost_expr = (
        1
        + fn.IIF(peer_total >= thresholds["p75"], 1, 0)
        + fn.IIF(peer_total >= thresholds["p90"], 3, 0)
        + fn.IIF(peer_total >= thresholds["p95"], 6, 0)
        + fn.IIF(peer_total >= thresholds["p99"], 10, 0)
    )
    weight_key = fn.ABS(fn.Random()) / boost_expr
    categories = base_categories + extra_categories

    query = (
        Torrent.select(
            Torrent.id,
            Torrent.name,
            Torrent.seeders,
            Torrent.leechers,
            Torrent.size,
            Torrent.category_id,
            Torrent.imdb,
            peer_total.alias("peers"),
        )
        .where(Torrent.category.in_(categories))
    )

    # Filter out fileless torrents by default
    if not include_fileless:
        # Check for actual file records in the files table
        file_exists_subquery = File.select().where(File.parentTorrent == Torrent.id)
        query = query.where(fn.EXISTS(file_exists_subquery))

    rows = list(query.order_by(weight_key).limit(limit))

    torrent_ids = [row.id for row in rows]
    file_map: dict[int, list[dict]] = {tid: [] for tid in torrent_ids}

    if torrent_ids:
        file_query = (
            File.select(File.parentTorrent, File.name, File.size)
            .where(File.parentTorrent.in_(torrent_ids))
            .dicts()
        )
        for file_row in file_query:
            parent_id = file_row["parentTorrent"]
            file_map[parent_id].append(
                {
                    "path": file_row["name"],
                    "size": int(file_row["size"]) if file_row["size"] is not None else None,
                }
            )

    for file_list in file_map.values():
        file_list.sort(key=lambda entry: (entry["size"] or -1), reverse=True)

    results = []
    for row in rows:
        # Determine type based on category
        if row.category_id in TV_CATEGORY_IDS:
            content_type = "tv"
        elif row.category_id in MOVIE_CATEGORY_IDS:
            content_type = "movie"
        else:
            # For other video categories (200, 204, 209), default to "movie"
            content_type = "movie"

        sample = {
            "name": row.name,
            "size": int(row.size) if row.size is not None else None,
            "imdb_id": row.imdb,
            "type": content_type,
            "files": file_map.get(row.id, []),
        }
        if include_sample_id:
            sample["sample_id"] = compute_sample_id(sample)
        results.append(sample)

    return results


def main() -> None:
    args = parse_args()
    include_category = tuple(args.include_category or ())

    # Parse split ratio if provided
    split_ratio = None
    if args.split_tv_film:
        try:
            split_ratio = parse_ratio(args.split_tv_film)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    with database:
        results = sample_torrents(
            args.limit,
            include_category,
            tv_only=args.tv,
            movie_only=args.movie,
            split_ratio=split_ratio,
            include_fileless=args.include_fileless,
            include_sample_id=args.sample_id,
        )

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
