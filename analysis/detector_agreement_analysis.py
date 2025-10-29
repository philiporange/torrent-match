#!/usr/bin/env python3
"""
Analyze detector agreement and consensus quality in the torrent ensemble.

This script examines how well detectors agree with each other:
- Pairwise agreement rates between detectors
- Consensus quality metrics
- Patterns in disagreement
- Impact of agreement on final confidence
"""

import json
import statistics
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple, Set
from pathlib import Path
from itertools import combinations


class DetectorAgreementAnalyzer:
    """Analyze detector agreement and consensus metrics."""

    def __init__(self, dataset_path: str):
        """Initialize with path to processed dataset."""
        self.dataset_path = Path(dataset_path)
        self.data = self._load_data()
        self.results = self.data['results']

    def _load_data(self) -> Dict[str, Any]:
        """Load and parse the dataset."""
        with open(self.dataset_path, 'r') as f:
            return json.load(f)

    def analyze_agreement(self) -> Dict[str, Any]:
        """Run complete agreement analysis."""
        print(f"Analyzing agreement across {len(self.results):,} samples...\n")

        analysis = {
            'consensus_metrics': self._analyze_consensus_metrics(),
            'pairwise_agreement': self._analyze_pairwise_agreement(),
            'agreement_patterns': self._analyze_agreement_patterns(),
            'confidence_correlation': self._analyze_confidence_correlation(),
            'disagreement_cases': self._analyze_disagreement_cases()
        }

        return analysis

    def _analyze_consensus_metrics(self) -> Dict[str, Any]:
        """Analyze overall consensus quality metrics."""
        consensus_samples = [
            r for r in self.results
            if 'metadata' in r and 'consensus' in r['metadata']
        ]

        if not consensus_samples:
            return {'error': 'No consensus samples found'}

        # Extract consensus metrics
        parser_counts = [r['metadata']['consensus']['parser_count'] for r in consensus_samples]
        title_agreements = [r['metadata']['consensus']['title_agreement'] for r in consensus_samples]
        agreement_ratios = [r['metadata']['consensus']['agreement_ratio'] for r in consensus_samples]
        avg_parser_confs = [r['metadata']['consensus']['avg_parser_confidence'] for r in consensus_samples]
        consensus_confs = [r['metadata']['consensus']['consensus_confidence'] for r in consensus_samples]

        # Agreement ratio bins
        agreement_bins = {
            'perfect (1.0)': sum(1 for a in agreement_ratios if a == 1.0),
            'high (0.75-0.99)': sum(1 for a in agreement_ratios if 0.75 <= a < 1.0),
            'medium (0.5-0.74)': sum(1 for a in agreement_ratios if 0.5 <= a < 0.75),
            'low (<0.5)': sum(1 for a in agreement_ratios if a < 0.5)
        }

        # Parser count distribution
        parser_count_dist = Counter(parser_counts)

        return {
            'total_consensus_samples': len(consensus_samples),
            'percentage_of_dataset': len(consensus_samples) / len(self.results),
            'parser_count_distribution': dict(parser_count_dist),
            'title_agreement': {
                'mean': statistics.mean(title_agreements),
                'median': statistics.median(title_agreements),
                'perfect_agreement': sum(1 for a in title_agreements if a == 1.0)
            },
            'agreement_ratio': {
                'mean': statistics.mean(agreement_ratios),
                'median': statistics.median(agreement_ratios),
                'min': min(agreement_ratios),
                'max': max(agreement_ratios),
                'std_dev': statistics.stdev(agreement_ratios) if len(agreement_ratios) > 1 else 0,
                'bins': agreement_bins
            },
            'avg_parser_confidence': {
                'mean': statistics.mean(avg_parser_confs),
                'median': statistics.median(avg_parser_confs),
                'min': min(avg_parser_confs),
                'max': max(avg_parser_confs)
            },
            'consensus_confidence': {
                'mean': statistics.mean(consensus_confs),
                'median': statistics.median(consensus_confs),
                'min': min(consensus_confs),
                'max': max(consensus_confs)
            }
        }

    def _analyze_pairwise_agreement(self) -> Dict[str, Any]:
        """Analyze agreement between each pair of detectors."""
        # Collect pairwise comparisons
        pairwise_data = defaultdict(lambda: {
            'both_present': 0,
            'title_matches': 0,
            'year_matches': 0,
            'both_match': 0,
            'confidence_diffs': []
        })

        for result in self.results:
            if 'metadata' not in result or 'parse_results' not in result['metadata']:
                continue

            parse_results = result['metadata']['parse_results']
            if len(parse_results) < 2:
                continue

            # Compare each pair of parsers
            for pr1, pr2 in combinations(parse_results, 2):
                parser1, parser2 = pr1['parser'], pr2['parser']
                pair_key = tuple(sorted([parser1, parser2]))

                pairwise_data[pair_key]['both_present'] += 1

                # Check title agreement
                title1 = (pr1.get('title') or '').lower().strip()
                title2 = (pr2.get('title') or '').lower().strip()
                if title1 and title2 and title1 == title2:
                    pairwise_data[pair_key]['title_matches'] += 1

                # Check year agreement
                year1 = pr1.get('year')
                year2 = pr2.get('year')
                if year1 and year2 and year1 == year2:
                    pairwise_data[pair_key]['year_matches'] += 1

                # Check if both match
                titles_match = title1 and title2 and title1 == title2
                years_match = (year1 is None and year2 is None) or (year1 == year2)
                if titles_match and years_match:
                    pairwise_data[pair_key]['both_match'] += 1

                # Track confidence differences
                conf_diff = abs(pr1['confidence'] - pr2['confidence'])
                pairwise_data[pair_key]['confidence_diffs'].append(conf_diff)

        # Calculate agreement rates
        pairwise_results = {}
        for pair, data in pairwise_data.items():
            if data['both_present'] == 0:
                continue

            pairwise_results[f"{pair[0]} <-> {pair[1]}"] = {
                'samples': data['both_present'],
                'title_agreement_rate': data['title_matches'] / data['both_present'],
                'year_agreement_rate': data['year_matches'] / data['both_present'] if data['year_matches'] > 0 else 0,
                'full_agreement_rate': data['both_match'] / data['both_present'],
                'avg_confidence_diff': statistics.mean(data['confidence_diffs']),
                'max_confidence_diff': max(data['confidence_diffs'])
            }

        # Rank pairs by agreement
        ranked_by_agreement = sorted(
            pairwise_results.items(),
            key=lambda x: x[1]['full_agreement_rate'],
            reverse=True
        )

        return {
            'pairwise_comparisons': pairwise_results,
            'ranked_by_agreement': ranked_by_agreement
        }

    def _analyze_agreement_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in agreement and disagreement."""
        # Collect samples by number of parsers agreeing
        by_parser_count = defaultdict(list)
        by_agreement_level = defaultdict(list)

        for result in self.results:
            if 'metadata' not in result or 'consensus' not in result['metadata']:
                continue

            consensus = result['metadata']['consensus']
            parser_count = consensus['parser_count']
            agreement_ratio = consensus['agreement_ratio']

            by_parser_count[parser_count].append(agreement_ratio)

            # Categorize by agreement level
            if agreement_ratio == 1.0:
                level = 'perfect'
            elif agreement_ratio >= 0.75:
                level = 'high'
            elif agreement_ratio >= 0.5:
                level = 'medium'
            else:
                level = 'low'
            by_agreement_level[level].append(result)

        # Calculate statistics by parser count
        parser_count_stats = {
            count: {
                'samples': len(agreements),
                'mean_agreement': statistics.mean(agreements),
                'perfect_agreement': sum(1 for a in agreements if a == 1.0),
                'perfect_agreement_rate': sum(1 for a in agreements if a == 1.0) / len(agreements)
            }
            for count, agreements in sorted(by_parser_count.items())
        }

        # Media type patterns
        media_type_agreement = defaultdict(list)
        for result in self.results:
            if 'metadata' in result and 'consensus' in result['metadata']:
                media_type = result['detected_type']
                agreement_ratio = result['metadata']['consensus']['agreement_ratio']
                media_type_agreement[media_type].append(agreement_ratio)

        media_type_stats = {
            media_type: {
                'samples': len(agreements),
                'mean_agreement': statistics.mean(agreements),
                'median_agreement': statistics.median(agreements)
            }
            for media_type, agreements in media_type_agreement.items()
        }

        return {
            'by_parser_count': parser_count_stats,
            'by_agreement_level': {
                level: len(samples) for level, samples in by_agreement_level.items()
            },
            'by_media_type': media_type_stats
        }

    def _analyze_confidence_correlation(self) -> Dict[str, Any]:
        """Analyze correlation between agreement and confidence."""
        # Collect data points
        data_points = []

        for result in self.results:
            if 'metadata' not in result or 'consensus' not in result['metadata']:
                continue

            consensus = result['metadata']['consensus']
            data_points.append({
                'agreement_ratio': consensus['agreement_ratio'],
                'final_confidence': result['confidence'],
                'consensus_confidence': consensus['consensus_confidence'],
                'avg_parser_confidence': consensus['avg_parser_confidence'],
                'parser_count': consensus['parser_count']
            })

        if not data_points:
            return {'error': 'No data points for correlation analysis'}

        # Calculate correlation (simple binned analysis)
        bins = {
            'perfect (1.0)': [],
            'high (0.75-0.99)': [],
            'medium (0.5-0.74)': [],
            'low (<0.5)': []
        }

        for dp in data_points:
            ratio = dp['agreement_ratio']
            if ratio == 1.0:
                bin_key = 'perfect (1.0)'
            elif ratio >= 0.75:
                bin_key = 'high (0.75-0.99)'
            elif ratio >= 0.5:
                bin_key = 'medium (0.5-0.74)'
            else:
                bin_key = 'low (<0.5)'
            bins[bin_key].append(dp['final_confidence'])

        correlation = {
            bin_key: {
                'count': len(confs),
                'mean_confidence': statistics.mean(confs) if confs else 0,
                'median_confidence': statistics.median(confs) if confs else 0
            }
            for bin_key, confs in bins.items()
        }

        return {
            'total_samples': len(data_points),
            'confidence_by_agreement_bin': correlation
        }

    def _analyze_disagreement_cases(self) -> Dict[str, Any]:
        """Analyze cases where detectors strongly disagree."""
        disagreement_cases = []

        for result in self.results:
            if 'metadata' not in result or 'parse_results' not in result['metadata']:
                continue

            parse_results = result['metadata']['parse_results']
            if len(parse_results) < 2:
                continue

            # Check for title disagreement
            titles = [(pr.get('title') or '').lower().strip() for pr in parse_results]
            unique_titles = set(t for t in titles if t)

            if len(unique_titles) > 1:
                # Multiple different titles extracted
                agreement_ratio = result['metadata'].get('consensus', {}).get('agreement_ratio', 0)

                disagreement_cases.append({
                    'sample_id': result['sample_id'],
                    'name': result['original_name'],
                    'agreement_ratio': agreement_ratio,
                    'unique_titles': list(unique_titles),
                    'title_count': len(unique_titles),
                    'parser_results': {
                        pr['parser']: {
                            'title': pr.get('title'),
                            'year': pr.get('year'),
                            'confidence': pr['confidence']
                        }
                        for pr in parse_results
                    }
                })

        # Sort by disagreement severity (low agreement ratio first)
        disagreement_cases.sort(key=lambda x: x['agreement_ratio'])

        # Categorize disagreements
        disagreement_types = {
            'severe (<0.5)': [c for c in disagreement_cases if c['agreement_ratio'] < 0.5],
            'moderate (0.5-0.74)': [c for c in disagreement_cases if 0.5 <= c['agreement_ratio'] < 0.75],
            'mild (0.75-0.99)': [c for c in disagreement_cases if 0.75 <= c['agreement_ratio'] < 1.0]
        }

        return {
            'total_disagreements': len(disagreement_cases),
            'disagreement_rate': len(disagreement_cases) / len(self.results),
            'by_severity': {
                severity: len(cases) for severity, cases in disagreement_types.items()
            },
            'top_disagreements': disagreement_cases[:30]
        }


def print_analysis(analysis: Dict[str, Any]):
    """Print formatted agreement analysis results."""
    print("\n" + "="*80)
    print("DETECTOR AGREEMENT & CONSENSUS ANALYSIS")
    print("="*80)

    # Consensus metrics
    print("\nCONSENSUS METRICS:")
    cm = analysis['consensus_metrics']
    if 'error' in cm:
        print(f"  {cm['error']}")
    else:
        print(f"  Total consensus samples: {cm['total_consensus_samples']:,} "
              f"({cm['percentage_of_dataset']*100:.1f}% of dataset)")

        print(f"\n  Parser count distribution:")
        for count, samples in sorted(cm['parser_count_distribution'].items()):
            pct = samples / cm['total_consensus_samples'] * 100
            print(f"    {count} parsers: {samples:6,} ({pct:5.1f}%)")

        print(f"\n  Title agreement:")
        ta = cm['title_agreement']
        print(f"    Mean: {ta['mean']:.3f}")
        print(f"    Median: {ta['median']:.3f}")
        print(f"    Perfect agreement: {ta['perfect_agreement']:,} "
              f"({ta['perfect_agreement']/cm['total_consensus_samples']*100:.1f}%)")

        print(f"\n  Overall agreement ratio:")
        ar = cm['agreement_ratio']
        print(f"    Mean: {ar['mean']:.3f}")
        print(f"    Median: {ar['median']:.3f}")
        print(f"    Range: [{ar['min']:.3f}, {ar['max']:.3f}]")
        print(f"    Std dev: {ar['std_dev']:.3f}")

        print(f"\n  Agreement distribution:")
        for bin_name, count in ar['bins'].items():
            pct = count / cm['total_consensus_samples'] * 100
            print(f"    {bin_name:20s}: {count:6,} ({pct:5.1f}%)")

        print(f"\n  Average parser confidence: {cm['avg_parser_confidence']['mean']:.3f}")
        print(f"  Consensus confidence: {cm['consensus_confidence']['mean']:.3f}")

    # Pairwise agreement
    print(f"\n" + "="*80)
    print("PAIRWISE DETECTOR AGREEMENT")
    print("="*80)

    pa = analysis['pairwise_agreement']
    print(f"\nTop 10 most agreeing detector pairs:")
    for i, (pair, stats) in enumerate(pa['ranked_by_agreement'][:10], 1):
        print(f"  {i}. {pair}")
        print(f"     Samples: {stats['samples']:,}")
        print(f"     Full agreement: {stats['full_agreement_rate']*100:.1f}%")
        print(f"     Title agreement: {stats['title_agreement_rate']*100:.1f}%")
        print(f"     Avg confidence diff: {stats['avg_confidence_diff']:.3f}")

    print(f"\nBottom 10 least agreeing detector pairs:")
    for i, (pair, stats) in enumerate(pa['ranked_by_agreement'][-10:], 1):
        print(f"  {i}. {pair}")
        print(f"     Samples: {stats['samples']:,}")
        print(f"     Full agreement: {stats['full_agreement_rate']*100:.1f}%")
        print(f"     Title agreement: {stats['title_agreement_rate']*100:.1f}%")
        print(f"     Avg confidence diff: {stats['avg_confidence_diff']:.3f}")

    # Agreement patterns
    print(f"\n" + "="*80)
    print("AGREEMENT PATTERNS")
    print("="*80)

    ap = analysis['agreement_patterns']
    print(f"\nBy parser count:")
    for count, stats in sorted(ap['by_parser_count'].items()):
        print(f"  {count} parsers: {stats['samples']:,} samples, "
              f"mean agreement={stats['mean_agreement']:.3f}, "
              f"perfect={stats['perfect_agreement_rate']*100:.1f}%")

    print(f"\nBy media type:")
    for media_type, stats in sorted(ap['by_media_type'].items()):
        print(f"  {media_type:20s}: {stats['samples']:,} samples, "
              f"mean={stats['mean_agreement']:.3f}, median={stats['median_agreement']:.3f}")

    # Confidence correlation
    print(f"\n" + "="*80)
    print("CONFIDENCE-AGREEMENT CORRELATION")
    print("="*80)

    cc = analysis['confidence_correlation']
    if 'error' in cc:
        print(f"  {cc['error']}")
    else:
        print(f"\nFinal confidence by agreement level:")
        for bin_name, stats in cc['confidence_by_agreement_bin'].items():
            if stats['count'] > 0:
                print(f"  {bin_name:20s}: {stats['count']:5,} samples, "
                      f"mean_conf={stats['mean_confidence']:.3f}, "
                      f"median={stats['median_confidence']:.3f}")

    # Disagreement cases
    print(f"\n" + "="*80)
    print("DISAGREEMENT ANALYSIS")
    print("="*80)

    dc = analysis['disagreement_cases']
    print(f"\nTotal disagreements: {dc['total_disagreements']:,} "
          f"({dc['disagreement_rate']*100:.1f}% of dataset)")

    print(f"\nBy severity:")
    for severity, count in dc['by_severity'].items():
        pct = count / dc['total_disagreements'] * 100 if dc['total_disagreements'] > 0 else 0
        print(f"  {severity:20s}: {count:6,} ({pct:5.1f}%)")

    print(f"\nTop 10 disagreement cases:")
    for i, case in enumerate(dc['top_disagreements'][:10], 1):
        print(f"\n  {i}. {case['name'][:70]}")
        print(f"     Agreement ratio: {case['agreement_ratio']:.3f}")
        print(f"     Unique titles: {case['title_count']}")
        for title in case['unique_titles']:
            print(f"       - {title}")
        print(f"     Parser results:")
        for parser, result in sorted(case['parser_results'].items()):
            print(f"       {parser:15s}: title=\"{result['title']}\" conf={result['confidence']:.2f}")


def save_analysis(analysis: Dict[str, Any], output_path: str):
    """Save analysis results to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(analysis, f, indent=2)
    print(f"\n\nAnalysis saved to: {output_path}")


def main():
    """Run detector agreement analysis."""
    import sys

    # Get dataset path from command line or use default
    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]
    else:
        dataset_path = '../processed_dataset.json'

    # Run analysis
    analyzer = DetectorAgreementAnalyzer(dataset_path)
    analysis = analyzer.analyze_agreement()

    # Print results
    print_analysis(analysis)

    # Save results
    output_path = Path(__file__).parent / 'detector_agreement_results.json'
    save_analysis(analysis, str(output_path))


if __name__ == '__main__':
    main()
