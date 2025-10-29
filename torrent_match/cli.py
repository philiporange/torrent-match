#!/usr/bin/env python3
"""
Command-line interface for torrent_match.

This module provides a comprehensive CLI for all torrent matching operations.
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .match import (
    TorrentMatcher,
    MediaIdentification,
    DatasetSample,
    set_verbose,
    init_from_env,
)
from .torrent_file_parser import TorrentFileParsingError


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog='torrent-match',
        description='Identify movies and TV shows from torrent names and file structures',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Identify a single torrent
  torrent-match identify "The.Matrix.1999.1080p.BluRay.x264"

  # Identify from a .torrent file
  torrent-match identify --torrent-file /path/to/file.torrent

  # With detailed output
  torrent-match identify "Inception.2010" --detail

  # Batch process from a file
  torrent-match batch torrents.txt --output results.json

  # Process a dataset
  torrent-match process-dataset dataset.json --output processed.json

  # Analyze processed results
  torrent-match analyze processed.json --output analysis.json

Environment Variables:
  TMDB_API_KEY       - TMDB API key for validation and enrichment
  LLM_API_KEY        - LLM API key for fallback parsing
  LLM_API_ENDPOINT   - LLM API endpoint (OpenRouter or OpenAI)
  LLM_MODEL          - LLM model to use
  USE_LLM_FALLBACK   - Enable LLM fallback (1/true/yes/on)
  VERBOSE            - Enable verbose logging (1/true/yes/on)
        """
    )

    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 0.1.0'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Identify command
    identify_parser = subparsers.add_parser(
        'identify',
        help='Identify a single torrent name or .torrent file',
        description='Identify media content from a torrent name or .torrent file'
    )
    identify_parser.add_argument(
        'name',
        nargs='?',
        help='Torrent name to identify (ignored when --torrent-file is provided)'
    )
    identify_parser.add_argument(
        '--files',
        nargs='+',
        help='Optional file paths (ignored when --torrent-file is set)'
    )
    identify_parser.add_argument(
        '--detail',
        action='store_true',
        help='Show detailed output with metadata'
    )
    identify_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    identify_parser.add_argument(
        '--enricher',
        action='store_true',
        help='Enable TMDB enricher for detailed metadata'
    )
    identify_parser.add_argument(
        '--torrent-file',
        type=Path,
        help='Path to a .torrent file to parse directly'
    )

    # Batch command
    batch_parser = subparsers.add_parser(
        'batch',
        help='Process multiple torrents from a file',
        description='Process multiple torrent names in parallel'
    )
    batch_parser.add_argument(
        'input',
        type=Path,
        help='Input file with one torrent name per line'
    )
    batch_parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output JSON file (default: stdout)'
    )
    batch_parser.add_argument(
        '--detail',
        action='store_true',
        help='Include detailed metadata'
    )
    batch_parser.add_argument(
        '--workers',
        type=int,
        default=5,
        help='Number of parallel workers (default: 5)'
    )
    batch_parser.add_argument(
        '--enricher',
        action='store_true',
        help='Enable TMDB enricher'
    )

    # Process dataset command
    process_parser = subparsers.add_parser(
        'process-dataset',
        help='Process a torrent dataset',
        description='Process dataset with id/input/output structure'
    )
    process_parser.add_argument(
        'dataset',
        type=Path,
        help='Path to dataset JSON file'
    )
    process_parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path('/tmp/torrent_match/processed_dataset.json'),
        help='Output JSON file (default: /tmp/torrent_match/processed_dataset.json)'
    )
    process_parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of samples to process'
    )
    process_parser.add_argument(
        '--save-interval',
        type=int,
        default=1000,
        help='Save intermediate results every N samples (default: 1000)'
    )
    process_parser.add_argument(
        '--enricher',
        action='store_true',
        help='Enable TMDB enricher'
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze processed dataset results',
        description='Generate comprehensive analysis and statistics'
    )
    analyze_parser.add_argument(
        'input',
        type=Path,
        help='Path to processed dataset JSON'
    )
    analyze_parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path('/tmp/torrent_match/analysis.json'),
        help='Output JSON file (default: /tmp/torrent_match/analysis.json)'
    )
    analyze_parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.8,
        help='Minimum confidence for flagging discrepancies (default: 0.8)'
    )

    # Test command
    test_parser = subparsers.add_parser(
        'test',
        help='Run the test suite',
        description='Run comprehensive tests on the dataset'
    )
    test_parser.add_argument(
        '--dataset',
        type=Path,
        default=Path('dataset.json'),
        help='Path to test dataset (default: dataset.json)'
    )
    test_parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of test samples'
    )

    return parser


def cmd_identify(args: argparse.Namespace) -> int:
    """Handle the identify command."""
    if args.verbose:
        set_verbose(True)
    else:
        init_from_env()

    matcher = TorrentMatcher(
        enable_enricher=args.enricher,
        verbose=args.verbose
    )

    result: Union[MediaIdentification, Dict[str, Any]]

    if args.torrent_file:
        torrent_path = args.torrent_file
        if not torrent_path.exists():
            print(f"Error: Torrent file {torrent_path} not found", file=sys.stderr)
            return 1
        try:
            result = matcher.match_torrent_file(torrent_path, detail=args.detail)
        except TorrentFileParsingError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    else:
        if not args.name:
            print("Error: provide a torrent name or use --torrent-file", file=sys.stderr)
            return 1
        result = matcher.match(args.name, args.files, detail=args.detail)

    if args.json or args.detail:
        output = result if isinstance(result, dict) else result.to_dict(detail=args.detail)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # Pretty print for human consumption
        print(f"Title: {result.title}")
        print(f"Year: {result.year}")
        if result.imdb_id:
            print(f"IMDB ID: {result.imdb_id}")
        if result.tmdb_id:
            print(f"TMDB ID: {result.tmdb_id}")
        print(f"Media Type: {result.media_type.value}")
        if result.season is not None:
            print(f"Season: {result.season}")
        if result.episode is not None:
            print(f"Episode: {result.episode}")
        print(f"Confidence: {result.confidence.name} ({result.confidence_value:.2f})")
        print(f"TMDB Match: {result.tmdb_match}")

    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """Handle the batch command."""
    if args.verbose:
        set_verbose(True)
    else:
        init_from_env()

    if not args.input.exists():
        print(f"Error: Input file {args.input} not found", file=sys.stderr)
        return 1

    # Read torrent names from file
    with args.input.open('r', encoding='utf-8') as f:
        torrents = [line.strip() for line in f if line.strip()]

    print(f"Processing {len(torrents)} torrents...", file=sys.stderr)

    matcher = TorrentMatcher(
        enable_enricher=args.enricher,
        verbose=args.verbose
    )

    results = matcher.match_batch(
        torrents,
        max_workers=args.workers,
        show_progress=True,
        detail=args.detail
    )

    # Convert to output format
    output = []
    for torrent_name, result in zip(torrents, results):
        if isinstance(result, dict):
            output.append({
                'input': torrent_name,
                'output': result
            })
        else:
            output.append({
                'input': torrent_name,
                'output': result.to_dict(detail=args.detail)
            })

    # Write output
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

    return 0


def cmd_process_dataset(args: argparse.Namespace) -> int:
    """Handle the process-dataset command."""
    if args.verbose:
        set_verbose(True)
    else:
        init_from_env()

    if not args.dataset.exists():
        print(f"Error: Dataset file {args.dataset} not found", file=sys.stderr)
        return 1

    # Import the process_dataset module
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from process_dataset import (
        load_dataset,
        create_detector,
        process_dataset,
        write_output,
        RunLogger
    )

    logger = RunLogger()
    samples, raw_data = load_dataset(args.dataset, logger)

    if args.limit:
        samples = samples[:args.limit]
        raw_data = raw_data[:args.limit]
        logger.log(f"Limited to {args.limit} samples")

    detector = create_detector(logger)

    # Override enricher setting if specified
    if args.enricher and not detector.tmdb_enricher:
        logger.log("Enricher requested but not enabled (TMDB_API_KEY required)")

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
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Handle the analyze command."""
    if args.verbose:
        set_verbose(True)
    else:
        init_from_env()

    if not args.input.exists():
        print(f"Error: Input file {args.input} not found", file=sys.stderr)
        return 1

    # Import the analyse_dataset module
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from analyse_dataset import (
        generate_summary,
        analyze_detection_accuracy,
        analyze_file_structure,
        analyze_episodes,
        analyze_parser_performance,
        analyze_confidence_distribution,
        analyze_media_types,
        find_discrepancies
    )

    print(f"Loading processed dataset from {args.input}...")
    with args.input.open('r', encoding='utf-8') as f:
        data = json.load(f)

    results = data.get('results', [])
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
        'summary': summary,
        'detection_accuracy': accuracy,
        'file_structure_analysis': file_structure,
        'episode_analysis': episodes,
        'parser_performance': parser_perf,
        'confidence_analysis': confidence,
        'media_type_analysis': media_types,
        'discrepancies': discrepancies,
    }

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    print(f"\nAnalysis written to {args.output}")
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """Handle the test command."""
    if args.verbose:
        set_verbose(True)
    else:
        init_from_env()

    if not args.dataset.exists():
        print(f"Error: Dataset file {args.dataset} not found", file=sys.stderr)
        return 1

    # Import and run the test module
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import test

    # Override sys.argv for the test module
    sys.argv = ['test.py', '--dataset', str(args.dataset)]
    if args.limit:
        sys.argv.extend(['--limit', str(args.limit)])

    # Run tests
    try:
        test.main()
        return 0
    except SystemExit as e:
        return e.code if e.code else 0


def main() -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handlers
    handlers = {
        'identify': cmd_identify,
        'batch': cmd_batch,
        'process-dataset': cmd_process_dataset,
        'analyze': cmd_analyze,
        'test': cmd_test,
    }

    handler = handlers.get(args.command)
    if handler:
        try:
            return handler(args)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user", file=sys.stderr)
            return 130
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
