# Torrent Detector Ensemble Analysis

Comprehensive analysis tools for evaluating the performance of the torrent content detector ensemble, focusing on individual detector performance and inter-detector agreement.

## Overview

The torrent detector is an ensemble of multiple parsers (GuessIt, PTN, ReBulk, Regex, and optionally LLM) that work together to identify media content from torrent names. This analysis suite provides deep insights into:

- **Individual Detector Performance**: How well each parser performs independently
- **Detector Agreement**: How much the parsers agree with each other
- **Consensus Quality**: Effectiveness of the ensemble's consensus mechanism
- **Disagreement Patterns**: Cases where parsers disagree and why

## Quick Start

Run the complete analysis suite:

```bash
cd analysis/
python run_analysis.py ../processed_dataset.json
```

Or run individual analyses:

```bash
# Individual detector performance
python individual_detector_analysis.py ../processed_dataset.json

# Detector agreement analysis
python detector_agreement_analysis.py ../processed_dataset.json
```

## Analysis Scripts

### 1. Individual Detector Analysis (`individual_detector_analysis.py`)

Analyzes each detector's performance independently.

**Metrics:**
- Detection success rates
- Confidence distributions per detector
- Title/year extraction rates
- Performance breakdown by media type (movies vs TV)
- Agreement with final consensus decisions
- Comparative rankings

**Usage:**
```bash
python individual_detector_analysis.py [dataset_path]
```

**Output:**
- Console report with detailed statistics
- `individual_detector_results.json` - Full analysis results

**Key Insights:**
- Which detector is most reliable
- Which detector handles specific content types best
- Confidence patterns across detectors
- Extraction success rates

### 2. Detector Agreement Analysis (`detector_agreement_analysis.py`)

Analyzes how well detectors agree with each other and the quality of consensus.

**Metrics:**
- Overall consensus quality metrics
- Pairwise agreement rates between all detector pairs
- Agreement patterns by parser count
- Agreement patterns by media type
- Confidence-agreement correlation
- Disagreement case analysis

**Usage:**
```bash
python detector_agreement_analysis.py [dataset_path]
```

**Output:**
- Console report with agreement statistics
- `detector_agreement_results.json` - Full analysis results

**Key Insights:**
- Which detector pairs agree most/least
- How agreement correlates with confidence
- Common disagreement patterns
- Severe disagreement cases requiring attention

### 3. Unified Analysis Runner (`run_analysis.py`)

Runs all analyses in sequence and generates a comprehensive report with combined insights.

**Features:**
- Executes all analysis modules
- Generates cross-analysis insights
- Provides actionable recommendations
- Creates timestamped results

**Usage:**
```bash
python run_analysis.py [dataset_path] [-o output_dir] [--no-json]
```

**Arguments:**
- `dataset_path`: Path to processed_dataset.json (default: ../processed_dataset.json)
- `-o, --output-dir`: Output directory for results (default: current directory)
- `--no-json`: Skip saving JSON output files

**Output:**
- Comprehensive console report
- `comprehensive_analysis_<timestamp>.json` - Combined results
- Executive summary with key findings and recommendations

## Understanding the Results

### Confidence Metrics

Confidence values range from 0.0 to 1.0:
- **HIGH** (≥0.8): Strong, reliable detection
- **MEDIUM** (≥0.6): Decent detection, may need validation
- **LOW** (≥0.4): Uncertain detection
- **VERY_LOW** (<0.4): Poor detection, likely incorrect

### Agreement Metrics

**Agreement Ratio**: Percentage of detectors that agree on the result
- **1.0**: Perfect agreement (all detectors agree)
- **0.75-0.99**: High agreement (most agree)
- **0.5-0.74**: Medium agreement (half or more agree)
- **<0.5**: Low agreement (significant disagreement)

**Title Agreement**: Specific to title field matching between detectors

**Consensus Confidence**: Final confidence computed from agreement and individual confidences

### Detector Names

- **GuessIt**: Primary parser, usually most accurate
- **PTN**: Secondary parser, good for common patterns
- **ReBulk**: Custom pattern matching
- **Regex**: Basic regex fallback
- **LLM**: AI-powered fallback (optional, for difficult cases)
- **Consensus(N)**: Final result from N detectors agreeing

## Example Workflow

1. **Run initial analysis:**
   ```bash
   python run_analysis.py ../processed_dataset.json
   ```

2. **Review the executive summary** to identify:
   - Overall ensemble effectiveness
   - Detector performance rankings
   - High disagreement cases
   - Recommendations for improvement

3. **Deep dive into specific areas:**
   ```bash
   # Focus on individual detector issues
   python individual_detector_analysis.py ../processed_dataset.json

   # Focus on agreement problems
   python detector_agreement_analysis.py ../processed_dataset.json
   ```

4. **Examine JSON outputs** for programmatic analysis:
   ```python
   import json
   with open('comprehensive_analysis_<timestamp>.json') as f:
       results = json.load(f)
   # Access specific metrics
   detectors = results['individual_detector']['individual_performance']
   ```

## Interpreting Results

### High Confidence Rate

If the ensemble achieves >80% HIGH confidence rate, the ensemble is performing well.

### Perfect Agreement Rate

If >70% of consensus samples have perfect agreement, the detectors are well-aligned.

### Disagreement Rate

If >20% of samples have disagreement, consider:
- Reviewing disagreement cases manually
- Adjusting parser weights
- Adding validation steps
- Training/improving weaker parsers

### Detector Rankings

Use the confidence rankings to identify:
- Most reliable detector (consider increasing its weight)
- Weakest detector (consider improving or removing)
- Complementary detectors (different strengths for different content)

## Advanced Analysis

### Custom Queries

The JSON outputs can be loaded and queried programmatically:

```python
import json

# Load results
with open('individual_detector_results.json') as f:
    results = json.load(f)

# Find detector with best TV show performance
tv_performance = {}
for detector, perf in results['individual_performance'].items():
    if 'performance_by_media_type' in perf:
        tv_stats = perf['performance_by_media_type'].get('tv_episode', {})
        if tv_stats:
            tv_performance[detector] = tv_stats['mean_confidence']

best_tv_detector = max(tv_performance.items(), key=lambda x: x[1])
print(f"Best TV detector: {best_tv_detector[0]} ({best_tv_detector[1]:.3f})")
```

### Filtering Samples

Identify specific problematic samples:

```python
# Find samples where detectors strongly disagree
disagreements = results['detector_agreement']['disagreement_cases']['top_disagreements']

# Filter by severity
severe = [d for d in disagreements if d['agreement_ratio'] < 0.5]

# Analyze patterns
print(f"Found {len(severe)} severe disagreements")
for case in severe[:5]:
    print(f"\n{case['name']}")
    print(f"  Agreement: {case['agreement_ratio']:.3f}")
    for parser, result in case['parser_results'].items():
        print(f"  {parser}: {result['title']} (conf={result['confidence']:.2f})")
```

## Output Files

All output files are timestamped to prevent overwriting:

- `individual_detector_results.json` - Individual performance analysis
- `detector_agreement_results.json` - Agreement analysis
- `comprehensive_analysis_YYYYMMDD_HHMMSS.json` - Complete analysis with insights

## Requirements

- Python 3.7+
- Dataset must be in the format produced by the torrent detector
- Required fields in dataset:
  - `sample_id`
  - `original_name`
  - `confidence`, `confidence_level`
  - `metadata.consensus` (for consensus samples)
  - `metadata.parse_results` (for multi-parser samples)

## Troubleshooting

**"No consensus samples found"**
- Verify dataset includes samples processed by multiple parsers
- Check that metadata fields are populated

**"No samples found for this detector"**
- Detector may not have been used in dataset
- Check parser names match exactly (case-sensitive)

**Performance is slow**
- Dataset may be very large
- Consider sampling a subset for faster iteration
- JSON parsing of large files can take time

## Future Enhancements

Potential additions to the analysis suite:
- Temporal analysis (performance over time)
- Error categorization (why parsers fail)
- False positive/negative analysis (with ground truth)
- Performance vs computational cost tradeoffs
- Ensemble optimization recommendations
- Visualization generation (plots, charts)

## License

CC0 - Public Domain

## Author

Philip Orange <git@philiporange.com>
