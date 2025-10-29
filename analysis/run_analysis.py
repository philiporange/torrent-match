#!/usr/bin/env python3
"""
Unified analysis runner for torrent detector ensemble performance.

Runs all analysis scripts and generates a comprehensive report on:
- Individual detector performance
- Detector agreement and consensus quality
- Overall ensemble effectiveness
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Import analysis modules
from individual_detector_analysis import DetectorPerformanceAnalyzer
from detector_agreement_analysis import DetectorAgreementAnalyzer


class UnifiedAnalysisRunner:
    """Runs all analyses and generates comprehensive reports."""

    def __init__(self, dataset_path: str, output_dir: str = None):
        """Initialize with dataset path and optional output directory."""
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir) if output_dir else Path(__file__).parent
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def run_all_analyses(self, save_json: bool = True) -> dict:
        """Run all analyses and return combined results."""
        print("="*80)
        print("COMPREHENSIVE TORRENT DETECTOR ENSEMBLE ANALYSIS")
        print("="*80)
        print(f"Dataset: {self.dataset_path}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        results = {
            'metadata': {
                'dataset_path': str(self.dataset_path),
                'timestamp': self.timestamp,
                'analyses_run': []
            }
        }

        # Run individual detector analysis
        print("\n\n" + "▶"*40)
        print("RUNNING INDIVIDUAL DETECTOR ANALYSIS")
        print("▶"*40)
        try:
            individual_analyzer = DetectorPerformanceAnalyzer(str(self.dataset_path))
            results['individual_detector'] = individual_analyzer.analyze_all_detectors()
            results['metadata']['analyses_run'].append('individual_detector')
            print("\n✓ Individual detector analysis completed")
        except Exception as e:
            print(f"\n✗ Individual detector analysis failed: {e}")
            results['individual_detector'] = {'error': str(e)}

        # Run agreement analysis
        print("\n\n" + "▶"*40)
        print("RUNNING DETECTOR AGREEMENT ANALYSIS")
        print("▶"*40)
        try:
            agreement_analyzer = DetectorAgreementAnalyzer(str(self.dataset_path))
            results['detector_agreement'] = agreement_analyzer.analyze_agreement()
            results['metadata']['analyses_run'].append('detector_agreement')
            print("\n✓ Detector agreement analysis completed")
        except Exception as e:
            print(f"\n✗ Detector agreement analysis failed: {e}")
            results['detector_agreement'] = {'error': str(e)}

        # Generate combined insights
        print("\n\n" + "▶"*40)
        print("GENERATING COMBINED INSIGHTS")
        print("▶"*40)
        try:
            results['combined_insights'] = self._generate_insights(results)
            print("\n✓ Combined insights generated")
        except Exception as e:
            print(f"\n✗ Combined insights generation failed: {e}")
            results['combined_insights'] = {'error': str(e)}

        # Save results
        if save_json:
            output_path = self.output_dir / f'comprehensive_analysis_{self.timestamp}.json'
            self._save_json(results, output_path)

        # Print summary
        self._print_summary(results)

        return results

    def _generate_insights(self, results: dict) -> dict:
        """Generate combined insights from all analyses."""
        insights = {
            'key_findings': [],
            'recommendations': [],
            'ensemble_effectiveness': {}
        }

        # Extract key metrics
        individual = results.get('individual_detector', {})
        agreement = results.get('detector_agreement', {})

        # Analyze ensemble effectiveness
        if 'dataset_info' in individual:
            dataset_info = individual['dataset_info']
            insights['ensemble_effectiveness']['total_samples'] = dataset_info['total_samples']
            insights['ensemble_effectiveness']['high_confidence_rate'] = (
                dataset_info['confidence_distribution'].get('HIGH', 0) /
                dataset_info['total_samples']
            )

        # Key findings from individual performance
        if 'individual_performance' in individual:
            best_detector = None
            best_conf = 0
            worst_detector = None
            worst_conf = 1.0

            for detector, perf in individual['individual_performance'].items():
                if 'error' in perf:
                    continue
                mean_conf = perf['confidence_stats']['mean']
                if mean_conf > best_conf:
                    best_conf = mean_conf
                    best_detector = detector
                if mean_conf < worst_conf:
                    worst_conf = mean_conf
                    worst_detector = detector

            if best_detector:
                insights['key_findings'].append(
                    f"Best performing detector: {best_detector} (mean confidence: {best_conf:.3f})"
                )
            if worst_detector:
                insights['key_findings'].append(
                    f"Weakest detector: {worst_detector} (mean confidence: {worst_conf:.3f})"
                )

        # Key findings from agreement analysis
        if 'consensus_metrics' in agreement and 'error' not in agreement['consensus_metrics']:
            cm = agreement['consensus_metrics']
            perfect_agreement_rate = (
                cm['title_agreement']['perfect_agreement'] /
                cm['total_consensus_samples']
            )
            insights['key_findings'].append(
                f"Perfect title agreement rate: {perfect_agreement_rate*100:.1f}%"
            )

            mean_agreement = cm['agreement_ratio']['mean']
            insights['key_findings'].append(
                f"Mean agreement ratio: {mean_agreement:.3f}"
            )

        # Recommendations based on findings
        if 'disagreement_cases' in agreement:
            dc = agreement['disagreement_cases']
            disagreement_rate = dc['disagreement_rate']

            if disagreement_rate > 0.2:
                insights['recommendations'].append(
                    f"High disagreement rate ({disagreement_rate*100:.1f}%) suggests need for "
                    "better parser alignment or weighting strategy"
                )

            severe_count = dc['by_severity'].get('severe (<0.5)', 0)
            if severe_count > 100:
                insights['recommendations'].append(
                    f"Found {severe_count} cases with severe disagreement - consider manual review "
                    "or additional validation step"
                )

        # Parser count recommendations
        if 'consensus_metrics' in agreement and 'error' not in agreement['consensus_metrics']:
            parser_dist = agreement['consensus_metrics']['parser_count_distribution']
            if parser_dist:
                max_count = max(parser_dist.keys())
                if max_count >= 4:
                    insights['recommendations'].append(
                        f"Using up to {max_count} parsers per sample - consider if all are necessary "
                        "for computational efficiency"
                    )

        # Agreement-confidence correlation insights
        if 'confidence_correlation' in agreement and 'error' not in agreement['confidence_correlation']:
            cc = agreement['confidence_correlation']['confidence_by_agreement_bin']
            if 'perfect (1.0)' in cc and 'low (<0.5)' in cc:
                perfect_conf = cc['perfect (1.0)']['mean_confidence']
                low_conf = cc['low (<0.5)']['mean_confidence']
                diff = perfect_conf - low_conf

                insights['key_findings'].append(
                    f"Confidence boost from perfect vs low agreement: {diff:.3f}"
                )

                if diff < 0.2:
                    insights['recommendations'].append(
                        "Low correlation between agreement and confidence - consider adjusting "
                        "consensus weighting algorithm"
                    )

        return insights

    def _print_summary(self, results: dict):
        """Print executive summary of all analyses."""
        print("\n\n" + "="*80)
        print("EXECUTIVE SUMMARY")
        print("="*80)

        # Combined insights
        if 'combined_insights' in results and 'error' not in results['combined_insights']:
            insights = results['combined_insights']

            print("\nKEY FINDINGS:")
            for i, finding in enumerate(insights['key_findings'], 1):
                print(f"  {i}. {finding}")

            if not insights['key_findings']:
                print("  (No key findings generated)")

            print("\nRECOMMENDATIONS:")
            for i, rec in enumerate(insights['recommendations'], 1):
                print(f"  {i}. {rec}")

            if not insights['recommendations']:
                print("  (No recommendations generated)")

            if insights['ensemble_effectiveness']:
                print("\nENSEMBLE EFFECTIVENESS:")
                for metric, value in insights['ensemble_effectiveness'].items():
                    if isinstance(value, float):
                        print(f"  {metric}: {value:.3f}")
                    else:
                        print(f"  {metric}: {value:,}")

        # Analysis completion status
        print("\n" + "="*80)
        print("ANALYSIS COMPLETION STATUS")
        print("="*80)

        metadata = results.get('metadata', {})
        analyses_run = metadata.get('analyses_run', [])

        print(f"\nCompleted analyses: {len(analyses_run)}")
        for analysis in analyses_run:
            status = '✓' if analysis in analyses_run else '✗'
            print(f"  {status} {analysis}")

        print(f"\nTimestamp: {metadata.get('timestamp', 'unknown')}")

    def _save_json(self, data: dict, output_path: Path):
        """Save analysis results to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n✓ Results saved to: {output_path}")


def main():
    """Main entry point for unified analysis."""
    parser = argparse.ArgumentParser(
        description='Run comprehensive torrent detector ensemble analysis'
    )
    parser.add_argument(
        'dataset',
        nargs='?',
        default='../processed_dataset.json',
        help='Path to processed dataset JSON file (default: ../processed_dataset.json)'
    )
    parser.add_argument(
        '-o', '--output-dir',
        help='Output directory for results (default: current directory)'
    )
    parser.add_argument(
        '--no-json',
        action='store_true',
        help='Do not save JSON output files'
    )

    args = parser.parse_args()

    # Verify dataset exists
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: Dataset file not found: {dataset_path}", file=sys.stderr)
        return 1

    # Run analyses
    runner = UnifiedAnalysisRunner(
        dataset_path=str(dataset_path),
        output_dir=args.output_dir
    )

    try:
        results = runner.run_all_analyses(save_json=not args.no_json)
        return 0
    except Exception as e:
        print(f"\n✗ Analysis failed with error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
