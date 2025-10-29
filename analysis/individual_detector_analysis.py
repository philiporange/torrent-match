#!/usr/bin/env python3
"""
Analyze individual detector performance in the torrent ensemble.

This script examines how each parser (GuessIt, PTN, ReBulk, Regex, LLM)
performs independently, including:
- Detection success rates
- Confidence distributions
- Error patterns
- Performance on different content types (movies vs TV)
"""

import json
import statistics
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple
from pathlib import Path


class DetectorPerformanceAnalyzer:
    """Analyze individual detector performance metrics."""

    def __init__(self, dataset_path: str):
        """Initialize with path to processed dataset."""
        self.dataset_path = Path(dataset_path)
        self.data = self._load_data()
        self.results = self.data['results']

    def _load_data(self) -> Dict[str, Any]:
        """Load and parse the dataset."""
        with open(self.dataset_path, 'r') as f:
            return json.load(f)

    def analyze_all_detectors(self) -> Dict[str, Any]:
        """Run complete analysis on all detectors."""
        print(f"Analyzing {len(self.results):,} samples...\n")

        # Get list of all detectors that appear in the dataset
        detectors = self._get_all_detectors()
        print(f"Found {len(detectors)} detectors: {', '.join(sorted(detectors))}\n")

        analysis = {
            'dataset_info': self._get_dataset_info(),
            'detector_usage': self._analyze_detector_usage(),
            'individual_performance': {},
            'comparative_analysis': {}
        }

        # Analyze each detector individually
        for detector in sorted(detectors):
            print(f"Analyzing {detector}...")
            analysis['individual_performance'][detector] = self._analyze_detector(detector)

        # Comparative analysis
        analysis['comparative_analysis'] = self._comparative_analysis(detectors, analysis)

        return analysis

    def _get_all_detectors(self) -> set:
        """Extract all unique detector names from the dataset."""
        detectors = set()

        for result in self.results:
            # Check parse_results in metadata
            if 'metadata' in result and 'parse_results' in result['metadata']:
                for parse_result in result['metadata']['parse_results']:
                    detectors.add(parse_result['parser'])

            # Also check parser_used field
            parser_used = result.get('parser_used', '')
            if parser_used and not parser_used.startswith('Consensus'):
                detectors.add(parser_used)

        return detectors

    def _get_dataset_info(self) -> Dict[str, Any]:
        """Get basic dataset statistics."""
        return {
            'total_samples': len(self.results),
            'media_types': dict(Counter(r['detected_type'] for r in self.results)),
            'confidence_distribution': dict(Counter(r['confidence_level'] for r in self.results)),
            'has_original_imdb': sum(1 for r in self.results if r.get('original_imdb_id')),
            'samples_with_consensus': sum(1 for r in self.results if 'Consensus' in r.get('parser_used', ''))
        }

    def _analyze_detector_usage(self) -> Dict[str, Any]:
        """Analyze how often each detector is used."""
        usage = defaultdict(int)
        as_primary = defaultdict(int)

        for result in self.results:
            parser_used = result.get('parser_used', '')

            # Count as primary (when not consensus)
            if parser_used and not parser_used.startswith('Consensus'):
                as_primary[parser_used] += 1

            # Count in consensus
            if 'metadata' in result and 'consensus' in result['metadata']:
                for parser in result['metadata']['consensus'].get('parsers_used', []):
                    usage[parser] += 1

        return {
            'total_usage': dict(usage),
            'as_primary_parser': dict(as_primary)
        }

    def _analyze_detector(self, detector: str) -> Dict[str, Any]:
        """Analyze performance of a single detector."""
        # Get all samples where this detector was used
        detector_results = []

        for result in self.results:
            if 'metadata' not in result or 'parse_results' not in result['metadata']:
                continue

            for parse_result in result['metadata']['parse_results']:
                if parse_result['parser'] == detector:
                    detector_results.append({
                        'sample': result,
                        'parse_result': parse_result
                    })

        if not detector_results:
            return {'error': 'No samples found for this detector'}

        # Compute metrics
        confidences = [r['parse_result']['confidence'] for r in detector_results]

        # Title extraction success
        titles_extracted = sum(1 for r in detector_results if r['parse_result'].get('title'))
        years_extracted = sum(1 for r in detector_results if r['parse_result'].get('year'))

        # Performance by media type
        by_media_type = defaultdict(list)
        for r in detector_results:
            media_type = r['sample']['detected_type']
            by_media_type[media_type].append(r['parse_result']['confidence'])

        # Agreement with consensus
        agrees_with_consensus = 0
        for r in detector_results:
            sample = r['sample']
            parse_result = r['parse_result']

            # Check if title matches detected title
            if parse_result.get('title') == sample.get('detected_title'):
                agrees_with_consensus += 1

        return {
            'samples_analyzed': len(detector_results),
            'confidence_stats': {
                'mean': statistics.mean(confidences),
                'median': statistics.median(confidences),
                'min': min(confidences),
                'max': max(confidences),
                'std_dev': statistics.stdev(confidences) if len(confidences) > 1 else 0
            },
            'extraction_rates': {
                'title_extracted': titles_extracted,
                'title_rate': titles_extracted / len(detector_results),
                'year_extracted': years_extracted,
                'year_rate': years_extracted / len(detector_results)
            },
            'performance_by_media_type': {
                media_type: {
                    'count': len(confs),
                    'mean_confidence': statistics.mean(confs),
                    'median_confidence': statistics.median(confs)
                }
                for media_type, confs in by_media_type.items()
            },
            'consensus_agreement': {
                'agrees_count': agrees_with_consensus,
                'agreement_rate': agrees_with_consensus / len(detector_results)
            }
        }

    def _comparative_analysis(self, detectors: set, all_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """Compare detectors against each other."""
        # Rank by mean confidence
        rankings = {}
        for detector in detectors:
            # Get performance from all_analysis or compute it
            if all_analysis and 'individual_performance' in all_analysis:
                perf = all_analysis['individual_performance'].get(detector)
            else:
                perf = self._analyze_detector(detector)

            if perf and 'error' not in perf:
                rankings[detector] = perf['confidence_stats']['mean']

        sorted_by_confidence = sorted(rankings.items(), key=lambda x: x[1], reverse=True)

        # Find samples where detectors disagree significantly
        high_disagreement_samples = []
        for result in self.results:
            if 'metadata' not in result or 'parse_results' not in result['metadata']:
                continue

            parse_results = result['metadata']['parse_results']
            if len(parse_results) < 2:
                continue

            confidences = [pr['confidence'] for pr in parse_results]
            if max(confidences) - min(confidences) > 0.3:  # Significant disagreement
                high_disagreement_samples.append({
                    'sample_id': result['sample_id'],
                    'name': result['original_name'],
                    'confidence_range': max(confidences) - min(confidences),
                    'parser_confidences': {
                        pr['parser']: pr['confidence'] for pr in parse_results
                    }
                })

        return {
            'confidence_rankings': sorted_by_confidence,
            'high_disagreement_count': len(high_disagreement_samples),
            'high_disagreement_samples': high_disagreement_samples[:20]  # Top 20
        }


def print_analysis(analysis: Dict[str, Any]):
    """Print formatted analysis results."""
    print("\n" + "="*80)
    print("INDIVIDUAL DETECTOR PERFORMANCE ANALYSIS")
    print("="*80)

    # Dataset info
    info = analysis['dataset_info']
    print(f"\nDATASET INFO:")
    print(f"  Total samples: {info['total_samples']:,}")
    print(f"  Samples with consensus: {info['samples_with_consensus']:,} "
          f"({info['samples_with_consensus']/info['total_samples']*100:.1f}%)")
    print(f"  Samples with original IMDB: {info['has_original_imdb']:,}")

    print(f"\n  Media type distribution:")
    for media_type, count in sorted(info['media_types'].items()):
        pct = count / info['total_samples'] * 100
        print(f"    {media_type:20s}: {count:6,} ({pct:5.1f}%)")

    print(f"\n  Confidence distribution:")
    for level in ['HIGH', 'MEDIUM', 'LOW', 'VERY_LOW']:
        count = info['confidence_distribution'].get(level, 0)
        pct = count / info['total_samples'] * 100
        print(f"    {level:10s}: {count:6,} ({pct:5.1f}%)")

    # Detector usage
    usage = analysis['detector_usage']
    print(f"\nDETECTOR USAGE:")
    print(f"  Total usage (including consensus):")
    for parser, count in sorted(usage['total_usage'].items(), key=lambda x: x[1], reverse=True):
        pct = count / info['total_samples'] * 100
        print(f"    {parser:15s}: {count:6,} ({pct:5.1f}%)")

    if usage['as_primary_parser']:
        print(f"\n  As primary parser (non-consensus):")
        for parser, count in sorted(usage['as_primary_parser'].items(), key=lambda x: x[1], reverse=True):
            pct = count / info['total_samples'] * 100
            print(f"    {parser:15s}: {count:6,} ({pct:5.1f}%)")

    # Individual performance
    print(f"\n" + "="*80)
    print("INDIVIDUAL DETECTOR PERFORMANCE")
    print("="*80)

    for detector, perf in sorted(analysis['individual_performance'].items()):
        if 'error' in perf:
            print(f"\n{detector}: {perf['error']}")
            continue

        print(f"\n{detector}:")
        print(f"  Samples: {perf['samples_analyzed']:,}")

        conf = perf['confidence_stats']
        print(f"  Confidence: mean={conf['mean']:.3f}, median={conf['median']:.3f}, "
              f"std={conf['std_dev']:.3f}, range=[{conf['min']:.3f}, {conf['max']:.3f}]")

        extr = perf['extraction_rates']
        print(f"  Extraction: title={extr['title_rate']*100:.1f}%, year={extr['year_rate']*100:.1f}%")

        print(f"  Consensus agreement: {perf['consensus_agreement']['agreement_rate']*100:.1f}%")

        if perf['performance_by_media_type']:
            print(f"  By media type:")
            for media_type, stats in sorted(perf['performance_by_media_type'].items()):
                print(f"    {media_type:20s}: {stats['count']:4,} samples, "
                      f"mean_conf={stats['mean_confidence']:.3f}")

    # Comparative analysis
    print(f"\n" + "="*80)
    print("COMPARATIVE ANALYSIS")
    print("="*80)

    comp = analysis['comparative_analysis']
    print(f"\nDetector ranking by mean confidence:")
    for i, (detector, conf) in enumerate(comp['confidence_rankings'], 1):
        print(f"  {i}. {detector:15s}: {conf:.3f}")

    print(f"\nHigh disagreement samples: {comp['high_disagreement_count']:,}")
    if comp['high_disagreement_samples']:
        print(f"\nTop disagreement cases:")
        for sample in comp['high_disagreement_samples'][:10]:
            print(f"  {sample['name'][:60]}")
            print(f"    Range: {sample['confidence_range']:.3f}")
            for parser, conf in sorted(sample['parser_confidences'].items(), key=lambda x: x[1], reverse=True):
                print(f"      {parser:15s}: {conf:.3f}")


def save_analysis(analysis: Dict[str, Any], output_path: str):
    """Save analysis results to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(analysis, f, indent=2)
    print(f"\nAnalysis saved to: {output_path}")


def main():
    """Run individual detector analysis."""
    import sys

    # Get dataset path from command line or use default
    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]
    else:
        dataset_path = '../processed_dataset.json'

    # Run analysis
    analyzer = DetectorPerformanceAnalyzer(dataset_path)
    analysis = analyzer.analyze_all_detectors()

    # Print results
    print_analysis(analysis)

    # Save results
    output_path = Path(__file__).parent / 'individual_detector_results.json'
    save_analysis(analysis, str(output_path))


if __name__ == '__main__':
    main()
