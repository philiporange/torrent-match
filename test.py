#!/usr/bin/env python3
"""
Test script for torrent content detector module.

This script evaluates the detector against the dataset.json file,
providing comprehensive analysis and performance metrics.
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict, Counter
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the module to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from torrent_detector import (
    TorrentContentDetector, DatasetSample, MediaType, ConfidenceLevel,
    set_verbose, init_from_env
)


def load_dataset(file_path: str, limit: int = None) -> List[DatasetSample]:
    """
    Load dataset from JSON file.

    Args:
        file_path: Path to dataset.json file
        limit: Optional limit on number of samples to load

    Returns:
        List of DatasetSample objects
    """
    print(f"Loading dataset from {file_path}...")

    with open(file_path, 'r') as f:
        data = json.load(f)

    if limit:
        data = data[:limit]
        print(f"Limited to {limit} samples")

    samples = [DatasetSample.from_dict(item) for item in data]
    print(f"Loaded {len(samples)} samples")

    return samples


def print_dataset_statistics(samples: List[DatasetSample]):
    """Print basic statistics about the dataset"""
    print("\n" + "="*60)
    print("DATASET STATISTICS")
    print("="*60)

    total = len(samples)
    tv_shows = sum(1 for s in samples if s.is_tv_show())
    movies = sum(1 for s in samples if s.is_movie())
    with_imdb = sum(1 for s in samples if s.has_imdb_id())
    without_imdb = total - with_imdb

    print(f"Total samples: {total}")
    print(f"TV shows: {tv_shows} ({tv_shows/total*100:.1f}%)")
    print(f"Movies: {movies} ({movies/total*100:.1f}%)")
    print(f"With IMDB ID: {with_imdb} ({with_imdb/total*100:.1f}%)")
    print(f"Without IMDB ID: {without_imdb} ({without_imdb/total*100:.1f}%)")


def test_basic_functionality(detector: TorrentContentDetector, samples: List[DatasetSample]):
    """Test basic functionality with a few samples"""
    print("\n" + "="*60)
    print("BASIC FUNCTIONALITY TEST")
    print("="*60)

    # Test with first few samples
    test_samples = samples[:5]

    for i, sample in enumerate(test_samples, 1):
        print(f"\n--- Test Sample {i} ---")
        print(f"Name: {sample.name}")
        print(f"Original IMDB ID: {sample.imdb_id}")
        print(f"Original Type: {sample.type}")

        # Identify content
        start_time = time.time()
        result = detector.identify(sample.name, sample.get_file_paths())
        end_time = time.time()

        print(f"Detected Title: {result.title}")
        print(f"Detected IMDB ID: {result.imdb_id}")
        print(f"Detected Type: {result.media_type.value}")
        print(f"Season: {result.season}, Episode: {result.episode}")
        print(f"Confidence: {result.confidence.name} ({result.confidence.value:.2f})")
        print(f"Parser: {result.parser_used}")
        print(f"TMDB Match: {result.tmdb_match}")
        print(f"Processing time: {end_time - start_time:.3f}s")

        # Check if IMDB ID matches (if both exist)
        if sample.imdb_id and result.imdb_id:
            match = sample.imdb_id == result.imdb_id
            print(f"IMDB ID Match: {match} ✅" if match else f"IMDB ID Match: {match} ❌")


def test_imdb_recovery(detector: TorrentContentDetector, samples: List[DatasetSample], limit: int = 50):
    """Test IMDB ID recovery for samples without them"""
    print("\n" + "="*60)
    print("IMDB ID RECOVERY TEST")
    print("="*60)

    # Filter samples without IMDB IDs
    missing_imdb = [s for s in samples if not s.has_imdb_id()][:limit]
    print(f"Testing IMDB recovery on {len(missing_imdb)} samples without IMDB IDs")

    if not missing_imdb:
        print("No samples without IMDB IDs found")
        return

    start_time = time.time()
    recovered = detector.recover_missing_imdb_ids(missing_imdb, max_workers=5)
    end_time = time.time()

    print(f"\nRecovered {len(recovered)} IMDB IDs in {end_time - start_time:.2f}s")
    print(f"Recovery rate: {len(recovered)/len(missing_imdb)*100:.1f}%")

    # Show some examples
    print("\n--- Recovered IMDB IDs Examples ---")
    for i, recovery in enumerate(recovered[:5], 1):
        print(f"{i}. {recovery['original_name']}")
        print(f"   -> {recovery['detected_title']} ({recovery['detected_year']})")
        print(f"   IMDB: {recovery['detected_imdb_id']} (confidence: {recovery['confidence']:.2f})")


def test_content_type_verification(detector: TorrentContentDetector, samples: List[DatasetSample], limit: int = 100):
    """Test content type verification"""
    print("\n" + "="*60)
    print("CONTENT TYPE VERIFICATION TEST")
    print("="*60)

    test_samples = samples[:limit]
    print(f"Testing content type verification on {len(test_samples)} samples")

    start_time = time.time()
    discrepancies = detector.verify_content_types(test_samples, max_workers=5)
    end_time = time.time()

    print(f"\nFound {len(discrepancies)} type discrepancies in {end_time - start_time:.2f}s")

    if discrepancies:
        print(f"Discrepancy rate: {len(discrepancies)/len(test_samples)*100:.1f}%")

        # Show some examples
        print("\n--- Type Discrepancies Examples ---")
        for i, disc in enumerate(discrepancies[:5], 1):
            print(f"{i}. {disc['original_name']}")
            print(f"   Original: {disc['original_type']} -> Detected: {disc['detected_type']}")
            print(f"   Confidence: {disc['confidence']:.2f} (Parser: {disc['parser_used']})")


def test_parser_performance(detector: TorrentContentDetector, samples: List[DatasetSample], limit: int = 20):
    """Test parser performance and accuracy"""
    print("\n" + "="*60)
    print("PARSER PERFORMANCE TEST")
    print("="*60)

    test_samples = samples[:limit]
    print(f"Testing parser performance on {len(test_samples)} samples")

    # Track parser usage and success rates
    parser_stats = defaultdict(lambda: {'total': 0, 'successful': 0, 'tmdb_matches': 0})

    start_time = time.time()
    results = detector.process_dataset_samples(test_samples, max_workers=5, show_progress=False)
    end_time = time.time()

    # Analyze results
    for result in results:
        parser = result['parser_used']
        parser_stats[parser]['total'] += 1

        if result['tmdb_match']:
            parser_stats[parser]['successful'] += 1
            parser_stats[parser]['tmdb_matches'] += 1
        elif result['confidence'] >= 0.5:
            parser_stats[parser]['successful'] += 1

    print(f"\nProcessed {len(test_samples)} samples in {end_time - start_time:.2f}s")
    print(f"Average time per sample: {(end_time - start_time)/len(test_samples):.3f}s")

    print("\n--- Parser Performance ---")
    for parser, stats in parser_stats.items():
        success_rate = stats['successful'] / stats['total'] * 100 if stats['total'] > 0 else 0
        tmdb_rate = stats['tmdb_matches'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"{parser}:")
        print(f"  Total: {stats['total']}")
        print(f"  Successful: {stats['successful']} ({success_rate:.1f}%)")
        print(f"  TMDB matches: {stats['tmdb_matches']} ({tmdb_rate:.1f}%)")


def test_confidence_distribution(detector: TorrentContentDetector, samples: List[DatasetSample], limit: int = 100):
    """Analyze confidence level distribution"""
    print("\n" + "="*60)
    print("CONFIDENCE DISTRIBUTION TEST")
    print("="*60)

    test_samples = samples[:limit]
    print(f"Analyzing confidence distribution on {len(test_samples)} samples")

    results = detector.process_dataset_samples(test_samples, max_workers=5, show_progress=False)

    # Count confidence levels
    confidence_counts = Counter(r['confidence_level'] for r in results)
    confidence_values = [r['confidence'] for r in results]

    print(f"\n--- Confidence Level Distribution ---")
    for level in ['VERY_LOW', 'LOW', 'MEDIUM', 'HIGH']:
        count = confidence_counts.get(level, 0)
        percentage = count / len(results) * 100
        print(f"{level}: {count} ({percentage:.1f}%)")

    print(f"\n--- Confidence Statistics ---")
    print(f"Average confidence: {sum(confidence_values)/len(confidence_values):.3f}")
    print(f"Min confidence: {min(confidence_values):.3f}")
    print(f"Max confidence: {max(confidence_values):.3f}")
    print(f"Median confidence: {sorted(confidence_values)[len(confidence_values)//2]:.3f}")


def test_file_structure_analysis(detector: TorrentContentDetector, samples: List[DatasetSample]):
    """Test file structure analysis capabilities"""
    print("\n" + "="*60)
    print("FILE STRUCTURE ANALYSIS TEST")
    print("="*60)

    # Find samples with interesting file structures
    season_folder_samples = []
    multi_file_samples = []
    single_file_samples = []

    for sample in samples[:50]:
        files = sample.get_file_paths()
        video_files = [f for f in files if any(f.endswith(ext) for ext in ['.mkv', '.mp4', '.avi'])]

        has_season_folders = any('season' in f.lower() or 's0' in f.lower() for f in files)

        if has_season_folders:
            season_folder_samples.append(sample)
        elif len(video_files) > 3:
            multi_file_samples.append(sample)
        elif len(video_files) == 1:
            single_file_samples.append(sample)

    print(f"Samples with season folders: {len(season_folder_samples)}")
    print(f"Samples with multiple video files: {len(multi_file_samples)}")
    print(f"Samples with single video file: {len(single_file_samples)}")

    # Test a few examples from each category
    categories = [
        ("Season Folders", season_folder_samples[:3]),
        ("Multiple Video Files", multi_file_samples[:3]),
        ("Single Video File", single_file_samples[:3])
    ]

    for category_name, test_samples in categories:
        if test_samples:
            print(f"\n--- {category_name} Examples ---")
            for sample in test_samples:
                content = detector.preprocessor.analyze_file_structure(sample.get_file_paths())
                result = detector.identify(sample.name, sample.get_file_paths())

                print(f"\nName: {sample.name}")
                print(f"Detected type: {content.media_type.value}")
                print(f"Has season folders: {content.has_season_folders}")
                print(f"Video files: {content.movie_file_count}")
                print(f"Final result: {result.media_type.value} (confidence: {result.confidence.value:.2f})")


def main(limit: int = None):
    """Main test function

    Args:
        limit: Optional limit on number of samples to test
    """
    print("Torrent Content Detector Test Suite")
    print("="*60)

    # Check for API keys
    tmdb_api_key = os.environ.get('TMDB_API_KEY')
    llm_api_key = os.environ.get('LLM_API_KEY')
    llm_api_endpoint = os.environ.get('LLM_API_ENDPOINT')
    llm_model = os.environ.get('LLM_MODEL')

    if not tmdb_api_key:
        print("Warning: TMDB_API_KEY not found in environment variables")
        print("IMDB ID recovery and validation will not be available")
        use_tmdb = False
    else:
        use_tmdb = True

    if llm_api_key:
        endpoint_info = llm_api_endpoint or 'OpenAI (default)'
        model_info = f"model: {llm_model}" if llm_model else "default model"
        print(f"LLM parser enabled with {endpoint_info}, {model_info}")
    else:
        print("LLM parser disabled (no LLM_API_KEY found)")

    # Initialize detector
    print("\nInitializing detector...")
    try:
        detector = TorrentContentDetector(
            tmdb_api_key=tmdb_api_key,
            llm_api_key=llm_api_key,
            llm_api_endpoint=llm_api_endpoint,
            llm_model=llm_model,
            use_llm_fallback=bool(llm_api_key),
            enable_caching=True  # Always enable caching with redislite
        )
    except Exception as e:
        print(f"Error initializing detector: {e}")
        return

    # Load dataset
    dataset_path = "dataset.json"
    if not os.path.exists(dataset_path):
        print(f"Error: {dataset_path} not found")
        return

    # Use a subset for testing (adjust as needed)
    samples = load_dataset(dataset_path, limit=limit if limit is not None else 200)
    print_dataset_statistics(samples)

    # Run tests
    test_basic_functionality(detector, samples)

    if use_tmdb:
        test_imdb_recovery(detector, samples, limit=30)
        test_content_type_verification(detector, samples, limit=50)

    test_parser_performance(detector, samples, limit=20)
    test_confidence_distribution(detector, samples, limit=50)
    test_file_structure_analysis(detector, samples)

    print("\n" + "="*60)
    print("TEST SUITE COMPLETED")
    print("="*60)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test script for torrent content detector"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug output"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of samples to test"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Initialize verbose flag from command line argument
    set_verbose(args.verbose)

    # Also initialize from environment variable as fallback
    init_from_env()

    main(limit=args.limit)