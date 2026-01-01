#!/usr/bin/env python3
"""
Torrent dataset processing with detection and enrichment.

This script processes torrent metadata from dataset.json and produces
a clean output structure with:
- id: Sample identifier
- input: Original dataset entry
- output: Detection results with detailed metadata

The output includes consensus-based title detection, TMDB validation,
and rich metadata including episodes, genres, ratings, and more.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from torrent_detector import (
    ConfidenceLevel,
    DatasetSample,
    MediaIdentification,
    MediaType,
    TorrentContentDetector,
)
from torrent_detector.file_structure_detector import FileStructureDetector
from torrent_detector.episode_extractor import EpisodeExtractor
from torrent_detector.verbose import init_from_env


DEFAULT_DATASET_PATH = Path(__file__).resolve().parent / "dataset.json"
DEFAULT_OUTPUT_PATH = Path("/tmp/torrent_match/comprehensive_dataset.json")


def iso_timestamp() -> str:
    """Return a human-readable UTC timestamp with millisecond precision."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class RunLogger:
    """Collect log records while printing them to stdout."""

    def __init__(self) -> None:
        self.records: List[str] = []

    def log(self, message: str) -> None:
        """Print a timestamped message and store it for later persistence."""
        line = f"[{iso_timestamp()}] {message}"
        self.records.append(line)
        print(line)

    def record_progress(self, message: str) -> None:
        """Store a progress-bar update message with a timestamp."""
        line = f"[{iso_timestamp()}] {message}"
        self.records.append(line)


@dataclass
class ProgressCounts:
    """Track cumulative statistics for the progress bar."""

    matches: int = 0
    recovered: int = 0
    errors: int = 0
    episodes_extracted: int = 0
    season_packs: int = 0


class ProgressBar:
    """Lightweight textual progress bar without external dependencies."""

    def __init__(
        self,
        total: int,
        logger: RunLogger,
        bar_length: int = 40,
    ) -> None:
        self.total = max(total, 1)
        self.logger = logger
        self.bar_length = bar_length
        self._rendered = False
        self._last_line_length = 0

    def clear_line(self) -> None:
        """Erase the current progress line so regular logging can continue."""
        if self._rendered:
            blank = " " * self._last_line_length
            sys.stdout.write("\r" + blank + "\r")
            sys.stdout.flush()
            self._rendered = False
            self._last_line_length = 0

    def render(self, completed: int, counts: ProgressCounts, elapsed: float) -> None:
        """Render the progress bar for the current state."""
        progress = min(max(completed / self.total, 0.0), 1.0)
        filled = int(self.bar_length * progress)
        bar = "#" * filled + "-" * (self.bar_length - filled)
        message = (
            f"Progress [{bar}] {progress * 100:5.1f}% "
            f"({completed}/{self.total}) | eps: {counts.episodes_extracted} | "
            f"seasons: {counts.season_packs} | errors: {counts.errors} | "
            f"elapsed: {elapsed:6.1f}s"
        )
        sys.stdout.write("\r" + message)
        sys.stdout.flush()
        self._rendered = True
        self._last_line_length = len(message)
        self.logger.record_progress(message)

    def finish(self) -> None:
        """Ensure the progress bar ends with a newline."""
        if self._rendered:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._rendered = False
            self._last_line_length = 0


def load_dataset(dataset_path: Path, logger: RunLogger) -> Tuple[List[DatasetSample], List[Dict[str, Any]]]:
    """Load dataset samples from disk and emit diagnostic logging."""
    logger.log(f"Loading dataset from {dataset_path}")
    with dataset_path.open("r", encoding="utf-8") as fp:
        raw_data = json.load(fp)
    samples = [DatasetSample.from_dict(entry) for entry in raw_data]
    logger.log(f"Loaded {len(samples)} samples from dataset")
    return samples, raw_data


def create_detector(logger: RunLogger, cache_path: Optional[str] = None) -> TorrentContentDetector:
    """Instantiate the TorrentContentDetector with environment-aware settings."""
    tmdb_api_key = os.getenv("TMDB_API_KEY")
    llm_api_key = os.getenv("LLM_API_KEY")
    llm_api_endpoint = os.getenv("LLM_API_ENDPOINT")
    llm_model = os.getenv("LLM_MODEL")
    use_llm_fallback = os.getenv("USE_LLM_FALLBACK", "false").lower() in ("1", "true", "yes", "on")

    if tmdb_api_key:
        logger.log("TMDB API key detected; TMDB validation is enabled")
    else:
        logger.log("No TMDB API key provided; TMDB validation will be skipped")

    if use_llm_fallback:
        if not llm_api_key:
            logger.log("USE_LLM_FALLBACK is set but no LLM_API_KEY was found; disabling LLM fallback")
            use_llm_fallback = False
        else:
            logger.log("LLM fallback is enabled")

    detector = TorrentContentDetector(
        tmdb_api_key=tmdb_api_key,
        llm_api_key=llm_api_key if use_llm_fallback else None,
        llm_api_endpoint=llm_api_endpoint if use_llm_fallback else None,
        llm_model=llm_model if use_llm_fallback else None,
        cache_db_path=cache_path or "/tmp/torrent_interpret_cache.db",
        use_llm_fallback=use_llm_fallback,
    )
    return detector


def process_sample_comprehensive(
    sample: DatasetSample,
    sample_dict: Dict[str, Any],
    detector: TorrentContentDetector,
    file_detector: FileStructureDetector,
    episode_extractor: EpisodeExtractor,
) -> Dict[str, Any]:
    """
    Process a single sample and return id/input/output structure.

    Args:
        sample: DatasetSample object for processing
        sample_dict: Original dictionary from dataset.json
        detector: TorrentContentDetector instance
        file_detector: FileStructureDetector instance
        episode_extractor: EpisodeExtractor instance

    Returns:
        Dictionary with 'id', 'input', and 'output' keys
    """
    try:
        # Run identification with file information
        identification = detector.identify(sample.name, sample.files)

        # Return simple id/input/output structure
        return {
            "id": sample.sample_id,
            "input": sample_dict,
            "output": identification.to_dict(detail=True),
        }

    except Exception as exc:
        return {
            "id": sample.sample_id,
            "input": sample_dict,
            "output": None,
            "error": str(exc),
        }


def process_dataset(
    detector: TorrentContentDetector,
    samples: List[DatasetSample],
    raw_data: List[Dict[str, Any]],
    logger: RunLogger,
    limit: Optional[int] = None,
    save_interval: int = 1000,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Process each dataset sample with simple id/input/output structure."""
    file_detector = FileStructureDetector()
    episode_extractor = EpisodeExtractor()

    total = len(samples) if limit is None else min(limit, len(samples))
    counts = ProgressCounts()
    progress_bar = ProgressBar(total=total, logger=logger)

    processed_results: List[Dict[str, Any]] = []
    start_time = time.time()

    for index, (sample, sample_dict) in enumerate(zip(samples[:total], raw_data[:total]), start=1):
        progress_bar.clear_line()

        result = process_sample_comprehensive(sample, sample_dict, detector, file_detector, episode_extractor)

        if result.get("error"):
            counts.errors += 1
            logger.log(f"Sample {result['id']} encountered an error: {result['error']}")
        else:
            output = result["output"]
            input_data = result["input"]

            # Update counts based on output
            if input_data.get("imdb_id") and output.get("imdb_id"):
                if input_data["imdb_id"] == output["imdb_id"]:
                    counts.matches += 1

            if not input_data.get("imdb_id") and output.get("imdb_id") and output.get("confidence", 0) >= 0.7:
                counts.recovered += 1

            # Count episodes if present in detail
            ep_count = 0
            if output.get("detail") and output["detail"].get("episode_summary"):
                ep_count = output["detail"]["episode_summary"].get("total_episodes", 0)
                if ep_count > 0:
                    counts.episodes_extracted += ep_count
                    if ep_count > 1:
                        counts.season_packs += 1

            logger.log(
                f"Processed {index}/{total} ({result['id']}) "
                f"-> {output.get('title', 'Unknown')} ({output.get('year', 'N/A')}) "
                f"| type: {output.get('media_type', 'unknown')} "
                f"| episodes: {ep_count} "
                f"| confidence: {output.get('confidence', 0):.2f}"
            )

        processed_results.append(result)
        elapsed = time.time() - start_time
        progress_bar.render(index, counts, elapsed)

        # Periodic saving every save_interval samples
        if save_interval > 0 and index % save_interval == 0 and output_path:
            progress_bar.clear_line()
            intermediate_summary = {
                "total_samples": index,
                "matches": counts.matches,
                "recovered": counts.recovered,
                "errors": counts.errors,
                "episodes_extracted": counts.episodes_extracted,
                "season_packs": counts.season_packs,
                "elapsed_seconds": round(time.time() - start_time, 2),
                "is_intermediate": True,
            }
            intermediate_payload = {
                "results": processed_results,
                "summary": intermediate_summary,
                "log": logger.records,
            }
            write_intermediate_output(output_path, intermediate_payload, logger, index)
            logger.log(f"Periodic save completed after {index} samples")

    progress_bar.finish()

    end_time = time.time()
    summary = {
        "total_samples": total,
        "matches": counts.matches,
        "recovered": counts.recovered,
        "errors": counts.errors,
        "episodes_extracted": counts.episodes_extracted,
        "season_packs": counts.season_packs,
        "elapsed_seconds": round(end_time - start_time, 2),
    }
    logger.log(
        "Processing complete: "
        f"{summary['total_samples']} samples | "
        f"{summary['matches']} matches | "
        f"{summary['recovered']} recovered | "
        f"{summary['episodes_extracted']} episodes extracted | "
        f"{summary['season_packs']} season packs | "
        f"{summary['errors']} errors | "
        f"elapsed {summary['elapsed_seconds']}s"
    )

    return {
        "results": processed_results,
        "summary": summary,
        "log": logger.records,
    }


def write_output(output_path: Path, payload: Dict[str, Any], logger: RunLogger) -> None:
    """Persist the aggregated run output to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
    logger.log(f"Wrote comprehensive dataset output to {output_path}")


def write_intermediate_output(output_path: Path, payload: Dict[str, Any], logger: RunLogger, sample_count: int) -> None:
    """Persist intermediate results to disk during processing."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
    logger.log(f"Saved intermediate progress after {sample_count} samples to {output_path}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Comprehensive torrent detection with ALL capabilities."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help=f"Path to the dataset JSON file (default: {DEFAULT_DATASET_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Destination for the processed dataset JSON (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optionally limit the number of samples processed (useful for debugging).",
    )
    parser.add_argument(
        "--cache-db",
        type=str,
        default=None,
        help="Override the detector cache database path.",
    )
    parser.add_argument(
        "--save-interval",
        type=int,
        default=1000,
        help="Save intermediate results every N samples (default: 1000, set to 0 to disable).",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    init_from_env()
    logger = RunLogger()

    if not args.dataset.exists():
        logger.log(f"Dataset file {args.dataset} does not exist")
        sys.exit(1)

    if args.save_interval > 0:
        logger.log(f"Periodic saving enabled: every {args.save_interval} samples")
    else:
        logger.log("Periodic saving disabled")

    logger.log("Starting torrent detection processing:")
    logger.log("  - Torrent name parsing with consensus-based confidence")
    logger.log("  - TMDB validation and enrichment")
    logger.log("  - Episode extraction for TV content")

    samples, raw_data = load_dataset(args.dataset, logger)
    detector = create_detector(logger, cache_path=args.cache_db)
    payload = process_dataset(
        detector,
        samples,
        raw_data,
        logger,
        limit=args.limit,
        save_interval=args.save_interval,
        output_path=args.output
    )
    write_output(args.output, payload, logger)


if __name__ == "__main__":
    main()
