#!/usr/bin/env python3
"""
Comprehensive analysis script for processed torrent dataset.

This script analyzes the output from process_dataset.py and generates
detailed statistics including:
- Detection accuracy metrics (IMDB matches, type matches)
- File structure analysis
- Episode extraction statistics
- Parser performance analysis
- Confidence distribution
- Missing episode detection
- Video file analysis

Input: Processed dataset with id/input/output structure
Output: Comprehensive analysis with metrics and statistics
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from torrent_detector import MediaType
from torrent_detector.file_structure_detector import FileStructureDetector
from torrent_detector.episode_extractor import EpisodeExtractor


DEFAULT_INPUT_PATH = Path("/tmp/torrent_match/comprehensive_dataset.json")
DEFAULT_OUTPUT_PATH = Path("/tmp/torrent_match/analysis_results.json")


def analyze_detection_accuracy(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze detection accuracy by comparing input vs output.

    Returns metrics on IMDB matches, type matches, and recovery rates.
    """
    total = len(results)
    imdb_matches = 0
    type_matches = 0
    imdb_recovered = 0
    missing_imdb_filled = 0

    for result in results:
        if result.get("error"):
            continue

        input_data = result["input"]
        output_data = result["output"]

        # IMDB ID match
        if input_data.get("imdb_id") and output_data.get("imdb_id"):
            if input_data["imdb_id"] == output_data["imdb_id"]:
                imdb_matches += 1

        # Type match (normalize both sides)
        input_type = input_data.get("type", "")
        output_type = output_data.get("media_type", "")

        # Normalize output type to match input format
        normalized_output = output_type.replace("_episode", "").replace("_season", "").replace("_multi_season", "").replace("_show", "")
        if normalized_output == "tv":
            normalized_output = "tv"

        if input_type == normalized_output:
            type_matches += 1

        # IMDB recovered (any IMDB found with good confidence)
        if output_data.get("imdb_id") and output_data.get("confidence", 0) >= 0.7:
            imdb_recovered += 1

        # Missing IMDB filled (specifically recovered for entries without one)
        if not input_data.get("imdb_id") and output_data.get("imdb_id") and output_data.get("confidence", 0) >= 0.7:
            missing_imdb_filled += 1

    return {
        "total_samples": total,
        "imdb_matches": imdb_matches,
        "imdb_match_rate": imdb_matches / total if total > 0 else 0,
        "type_matches": type_matches,
        "type_match_rate": type_matches / total if total > 0 else 0,
        "imdb_recovered": imdb_recovered,
        "imdb_recovery_rate": imdb_recovered / total if total > 0 else 0,
        "missing_imdb_filled": missing_imdb_filled,
        "missing_fill_rate": missing_imdb_filled / total if total > 0 else 0,
    }


def analyze_file_structure(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze file structure characteristics across the dataset.
    """
    file_detector = FileStructureDetector()

    file_type_counts = Counter()
    has_dominant_file = 0
    has_season_folders = 0
    multi_video_files = 0

    video_file_counts = []
    dominant_ratios = []

    for result in results:
        if result.get("error"):
            continue

        input_data = result["input"]
        files = input_data.get("files", [])

        # Convert to detector format
        files_for_detector = [
            {"path": f.get("path", ""), "length": f.get("size", 0)}
            for f in files
        ]

        # Detect media type
        media_type = file_detector.detect_media_type(files_for_detector, input_data.get("name", ""))
        file_type_counts[media_type.value] += 1

        # Get video summary
        summary = file_detector.get_video_file_summary(files_for_detector)
        video_file_counts.append(summary["count"])

        if summary["has_dominant_file"]:
            has_dominant_file += 1
            dominant_ratios.append(summary["dominant_ratio"])

        if summary["season_folders"] > 0:
            has_season_folders += 1

        if summary["count"] > 1:
            multi_video_files += 1

    total = len(results)

    return {
        "file_type_distribution": dict(file_type_counts),
        "has_dominant_file_count": has_dominant_file,
        "has_dominant_file_rate": has_dominant_file / total if total > 0 else 0,
        "has_season_folders_count": has_season_folders,
        "has_season_folders_rate": has_season_folders / total if total > 0 else 0,
        "multi_video_files_count": multi_video_files,
        "multi_video_files_rate": multi_video_files / total if total > 0 else 0,
        "avg_video_files": sum(video_file_counts) / len(video_file_counts) if video_file_counts else 0,
        "avg_dominant_ratio": sum(dominant_ratios) / len(dominant_ratios) if dominant_ratios else 0,
    }


def analyze_episodes(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze episode extraction across TV content.
    """
    episode_extractor = EpisodeExtractor()

    total_episodes_extracted = 0
    season_pack_count = 0
    multi_season_pack_count = 0
    single_episode_count = 0

    episodes_per_season_pack = []
    seasons_per_pack = []
    missing_episode_instances = 0

    for result in results:
        if result.get("error"):
            continue

        input_data = result["input"]
        output_data = result["output"]

        # Only analyze TV content
        if output_data.get("medium") != "TV":
            continue

        files = input_data.get("files", [])
        files_for_extractor = [
            {"path": f.get("path", ""), "length": f.get("size", 0)}
            for f in files
        ]

        # Extract episodes
        episodes = episode_extractor.extract_episodes(files_for_extractor)
        episode_summary = episode_extractor.get_episode_count_summary(files_for_extractor)
        missing = episode_extractor.detect_missing_episodes(files_for_extractor)

        ep_count = episode_summary.get("total_episodes", 0)
        season_count = episode_summary.get("season_count", 0)

        total_episodes_extracted += ep_count

        if ep_count == 1:
            single_episode_count += 1
        elif ep_count > 1:
            if season_count == 1:
                season_pack_count += 1
                episodes_per_season_pack.append(ep_count)
            elif season_count > 1:
                multi_season_pack_count += 1
                seasons_per_pack.append(season_count)
                episodes_per_season_pack.append(ep_count)

        if missing:
            missing_episode_instances += 1

    return {
        "total_episodes_extracted": total_episodes_extracted,
        "single_episode_count": single_episode_count,
        "season_pack_count": season_pack_count,
        "multi_season_pack_count": multi_season_pack_count,
        "missing_episode_instances": missing_episode_instances,
        "avg_episodes_per_season_pack": sum(episodes_per_season_pack) / len(episodes_per_season_pack) if episodes_per_season_pack else 0,
        "avg_seasons_per_pack": sum(seasons_per_pack) / len(seasons_per_pack) if seasons_per_pack else 0,
    }


def analyze_parser_performance(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze parser performance and consensus patterns.
    """
    parser_usage = Counter()
    confidence_levels = Counter()
    tmdb_match_count = 0

    consensus_counts = []
    agreement_ratios = []

    for result in results:
        if result.get("error"):
            continue

        output_data = result["output"]
        detail = output_data.get("detail", {})

        # Parser usage
        parser_used = detail.get("parser_used", "Unknown")
        parser_usage[parser_used] += 1

        # Confidence levels
        confidence_level = detail.get("confidence_level", "UNKNOWN")
        confidence_levels[confidence_level] += 1

        # TMDB matches
        if output_data.get("tmdb_match"):
            tmdb_match_count += 1

        # Consensus data
        consensus = detail.get("consensus", {})
        if consensus:
            consensus_counts.append(consensus.get("parser_count", 0))
            agreement_ratios.append(consensus.get("agreement_ratio", 0))

    total = len(results)

    return {
        "parser_usage": dict(parser_usage),
        "confidence_distribution": dict(confidence_levels),
        "tmdb_match_count": tmdb_match_count,
        "tmdb_match_rate": tmdb_match_count / total if total > 0 else 0,
        "avg_parsers_used": sum(consensus_counts) / len(consensus_counts) if consensus_counts else 0,
        "avg_agreement_ratio": sum(agreement_ratios) / len(agreement_ratios) if agreement_ratios else 0,
    }


def analyze_confidence_distribution(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze detailed confidence score distribution.
    """
    confidence_scores = []

    for result in results:
        if result.get("error"):
            continue

        output_data = result["output"]
        confidence = output_data.get("confidence", 0)
        confidence_scores.append(confidence)

    if not confidence_scores:
        return {
            "count": 0,
            "mean": 0,
            "median": 0,
            "min": 0,
            "max": 0,
        }

    confidence_scores.sort()
    n = len(confidence_scores)

    return {
        "count": n,
        "mean": sum(confidence_scores) / n,
        "median": confidence_scores[n // 2],
        "min": confidence_scores[0],
        "max": confidence_scores[-1],
        "percentile_25": confidence_scores[n // 4],
        "percentile_75": confidence_scores[3 * n // 4],
    }


def analyze_media_types(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze media type distribution.
    """
    input_types = Counter()
    output_types = Counter()

    for result in results:
        if result.get("error"):
            continue

        input_data = result["input"]
        output_data = result["output"]

        input_types[input_data.get("type", "unknown")] += 1
        output_types[output_data.get("media_type", "unknown")] += 1

    return {
        "input_type_distribution": dict(input_types),
        "output_type_distribution": dict(output_types),
    }


def find_discrepancies(results: List[Dict[str, Any]], min_confidence: float = 0.8) -> List[Dict[str, Any]]:
    """
    Find samples where detection disagrees with input metadata.
    """
    discrepancies = []

    for result in results:
        if result.get("error"):
            continue

        input_data = result["input"]
        output_data = result["output"]

        # Only flag high-confidence discrepancies
        if output_data.get("confidence", 0) < min_confidence:
            continue

        issues = []

        # IMDB mismatch
        if input_data.get("imdb_id") and output_data.get("imdb_id"):
            if input_data["imdb_id"] != output_data["imdb_id"]:
                issues.append({
                    "type": "imdb_mismatch",
                    "input_value": input_data["imdb_id"],
                    "output_value": output_data["imdb_id"],
                })

        # Type mismatch
        input_type = input_data.get("type", "")
        output_type = output_data.get("media_type", "")
        normalized_output = output_type.replace("_episode", "").replace("_season", "").replace("_multi_season", "").replace("_show", "")

        if input_type != normalized_output:
            issues.append({
                "type": "type_mismatch",
                "input_value": input_type,
                "output_value": output_type,
            })

        if issues:
            discrepancies.append({
                "id": result["id"],
                "name": input_data.get("name"),
                "confidence": output_data.get("confidence"),
                "issues": issues,
            })

    return discrepancies


def generate_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate overall summary statistics.
    """
    total = len(results)
    errors = sum(1 for r in results if r.get("error"))
    successful = total - errors

    return {
        "total_samples": total,
        "successful": successful,
        "errors": errors,
        "success_rate": successful / total if total > 0 else 0,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze processed torrent dataset"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"Path to processed dataset JSON (default: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path to output analysis JSON (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.8,
        help="Minimum confidence for flagging discrepancies (default: 0.8)",
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file {args.input} does not exist")
        sys.exit(1)

    print(f"Loading processed dataset from {args.input}...")
    with args.input.open("r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])
    print(f"Loaded {len(results)} results")

    print("\nPerforming comprehensive analysis...")

    # Run all analyses
    summary = generate_summary(results)
    accuracy = analyze_detection_accuracy(results)
    file_structure = analyze_file_structure(results)
    episodes = analyze_episodes(results)
    parser_perf = analyze_parser_performance(results)
    confidence = analyze_confidence_distribution(results)
    media_types = analyze_media_types(results)
    discrepancies = find_discrepancies(results, min_confidence=args.min_confidence)

    print(f"\nAnalysis complete:")
    print(f"  - Total samples: {summary['total_samples']}")
    print(f"  - Successful: {summary['successful']}")
    print(f"  - IMDB match rate: {accuracy['imdb_match_rate']:.1%}")
    print(f"  - Type match rate: {accuracy['type_match_rate']:.1%}")
    print(f"  - Episodes extracted: {episodes['total_episodes_extracted']}")
    print(f"  - Discrepancies found: {len(discrepancies)}")

    # Build analysis output
    analysis = {
        "summary": summary,
        "detection_accuracy": accuracy,
        "file_structure_analysis": file_structure,
        "episode_analysis": episodes,
        "parser_performance": parser_perf,
        "confidence_analysis": confidence,
        "media_type_analysis": media_types,
        "discrepancies": discrepancies,
    }

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    print(f"\nAnalysis written to {args.output}")


if __name__ == "__main__":
    main()
