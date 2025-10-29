"""
Compute descriptive statistics for peer counts across video torrents.

This script reuses the shared Peewee ORM in `models.py`, initialises the
database connection in read-only mode, restricts to movie/TV categories, and
derives summary metrics (count, total peers, mean/median, extrema, selected
percentiles, variance). The results are written to `/tmp/test/peer_stats.json`,
which can be consumed to tune sampling strategies elsewhere in the project.
"""

from __future__ import annotations

import json
import math
from array import array
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Tuple

from models import Torrent, init_sqlite_database


PROJECT_NAME = "test"
OUTPUT_PATH = Path(f"/tmp/{PROJECT_NAME}/peer_stats.json")
VIDEO_CATEGORY_IDS = (
    200,
    201,
    202,
    204,
    205,
    207,
    208,
    209,
)

database = init_sqlite_database(read_only=True)


def ensure_output_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def iter_peer_counts() -> Iterable[Tuple[int, int]]:
    query = (
        Torrent.select(Torrent.category_id, Torrent.seeders, Torrent.leechers)
        .where(Torrent.category.in_(VIDEO_CATEGORY_IDS))
        .iterator()
    )
    for row in query:
        seeders = int(row.seeders or 0)
        leechers = int(row.leechers or 0)
        peers = max(seeders + leechers, 0)
        yield row.category_id, peers


def compute_stats() -> Dict[str, object]:
    peers_array = array("I")
    category_counts: Dict[str, int] = defaultdict(int)
    total_peers = 0
    total_count = 0
    sum_sq = 0
    min_peers: int | None = None
    max_peers: int | None = None

    for category, peers in iter_peer_counts():
        peers_array.append(peers)
        total_peers += peers
        sum_sq += peers * peers
        total_count += 1
        category_counts[str(category)] += 1

        if min_peers is None or peers < min_peers:
            min_peers = peers
        if max_peers is None or peers > max_peers:
            max_peers = peers

    if total_count == 0:
        return {
            "total_torrents": 0,
            "total_peers": 0,
            "mean_peers": 0.0,
            "median_peers": None,
            "min_peers": None,
            "max_peers": None,
            "stddev_peers": 0.0,
            "percentiles": {},
            "category_counts": {},
            "video_category_ids": VIDEO_CATEGORY_IDS,
        }

    mean = total_peers / total_count
    variance = max((sum_sq / total_count) - mean**2, 0.0)
    stddev = math.sqrt(variance)

    sorted_peers = sorted(peers_array)

    def percentile(rank: float) -> float:
        position = rank * (total_count - 1)
        lower_index = int(math.floor(position))
        upper_index = int(math.ceil(position))
        lower_val = sorted_peers[lower_index]
        upper_val = sorted_peers[upper_index]
        if lower_index == upper_index:
            return float(lower_val)
        weight = position - lower_index
        return lower_val * (1.0 - weight) + upper_val * weight

    percentiles = {
        "p10": percentile(0.10),
        "p25": percentile(0.25),
        "p50": percentile(0.50),
        "p75": percentile(0.75),
        "p90": percentile(0.90),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
    }

    return {
        "total_torrents": total_count,
        "total_peers": total_peers,
        "mean_peers": mean,
        "median_peers": percentiles["p50"],
        "min_peers": min_peers,
        "max_peers": max_peers,
        "stddev_peers": stddev,
        "percentiles": percentiles,
        "category_counts": category_counts,
        "video_category_ids": VIDEO_CATEGORY_IDS,
    }


def main() -> None:
    ensure_output_dir(OUTPUT_PATH)

    with database:
        stats = compute_stats()

    OUTPUT_PATH.write_text(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
