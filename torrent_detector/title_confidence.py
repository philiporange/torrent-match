"""
Title confidence scoring based on weighted parser consensus.

This module implements a consensus-based confidence system that focuses ENTIRELY
on parser agreement for title extraction. The confidence score reflects "how sure
we are that the detected title is correct," based ONLY on weighted agreement
across parsers.

Key principles:
- Higher-trust parsers (GuessIt, PTN) have more influence on confidence
- Lower-trust parsers (Regex) have minimal impact
- Parser-provided confidence values are INTENTIONALLY IGNORED
- Only title agreement matters - no TMDB, year, episodes, or file structure
- If only weak parsers agree, confidence stays low
- If strong parsers disagree, confidence cannot be high

The output is a single confidence score that represents title certainty.
"""

import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
from .models import ParseResult, ConfidenceLevel


# Parser trust weights: higher = more reliable for title extraction
PARSER_TRUST = {
    "GuessIt": 1.0,      # Most reliable for title
    "PTN": 0.8,          # Very good secondary parser
    "ReBulk": 0.6,       # Decent pattern matching
    "LLM": 0.5,          # Good on weird cases but can hallucinate
    "Regex": 0.2,        # Noisy, last resort
}


def clean_candidate_title(raw_title: str) -> str:
    """
    Clean a parser's raw title output by removing obvious metadata junk.

    This removes years, quality indicators, season/episode markers, and other
    non-title content that parsers sometimes include in their title field.

    Args:
        raw_title: Raw title string from parser

    Returns:
        Cleaned title with metadata stripped
    """
    if not raw_title:
        return ""

    title = raw_title.strip()

    # Remove common separators at start/end
    title = title.strip('.-_ ')

    # Remove trailing year patterns like "2023" or "(2023)"
    title = re.sub(r'\s*[\(\[]?\d{4}[\)\]]?\s*$', '', title)

    # Remove quality indicators (1080p, 720p, BluRay, WEB-DL, etc.)
    quality_pattern = r'\b(1080p|720p|480p|2160p|4K|BluRay|BRRip|WEB-DL|WEBRip|HDTV|DVDRip|XviD|x264|x265|HEVC|10bit)\b'
    title = re.sub(quality_pattern, '', title, flags=re.IGNORECASE)

    # Remove season/episode markers if they appear at the end
    # e.g., "Breaking Bad S01", "Matrix Season 1"
    season_pattern = r'\s+(?:S(?:eason)?\s*\d+|Complete\s+Season).*$'
    title = re.sub(season_pattern, '', title, flags=re.IGNORECASE)

    # Remove episode markers at the end
    episode_pattern = r'\s+(?:E(?:pisode)?\s*\d+|Ep\s*\d+).*$'
    title = re.sub(episode_pattern, '', title, flags=re.IGNORECASE)

    # Remove source indicators (WEB, DVD, etc.) if at end
    title = re.sub(r'\s+(?:WEB|DVD|BD|BluRay|HDTV).*$', '', title, flags=re.IGNORECASE)

    # Collapse multiple spaces
    title = re.sub(r'\s+', ' ', title).strip()

    return title


def normalize_title_for_vote(clean_title: str) -> str:
    """
    Normalize a cleaned title for voting/grouping purposes.

    This collapses trivial differences like capitalization, punctuation,
    and leading articles so that "The Matrix", "Matrix", and "the.matrix"
    are all considered the same title for consensus purposes.

    Args:
        clean_title: Title already cleaned of metadata

    Returns:
        Normalized title for grouping
    """
    if not clean_title:
        return ""

    # Lowercase
    title = clean_title.lower()

    # Remove punctuation and separators, replace with spaces
    title = re.sub(r'[^a-z0-9\s]', ' ', title)

    # Collapse whitespace
    title = re.sub(r'\s+', ' ', title).strip()

    # Remove leading articles (the, a, an)
    title = re.sub(r'^(the|a|an)\s+', '', title)

    return title


def compute_title_votes(parse_results: List[ParseResult]) -> Dict[str, Dict[str, Any]]:
    """
    Build vote table from parser results.

    Each parser votes for a title with weight based on its trust level.
    Titles are normalized for grouping, and we track the original forms
    and which parsers voted for each normalized title.

    Args:
        parse_results: List of all parser results

    Returns:
        Dictionary mapping normalized_title -> {
            'total_weight': float,
            'voters': List[str],
            'raw_titles': set of original title strings,
        }
    """
    votes = defaultdict(lambda: {
        'total_weight': 0.0,
        'voters': [],
        'raw_titles': set(),
    })

    for result in parse_results:
        if not result.title:
            continue

        # Clean and normalize the title
        cleaned = clean_candidate_title(result.title)
        if not cleaned:
            continue

        normalized = normalize_title_for_vote(cleaned)
        if not normalized:
            continue

        # Get parser trust weight
        parser_name = result.parser_name
        weight = PARSER_TRUST.get(parser_name, 0.3)  # Default to low trust if unknown

        # Cast vote
        votes[normalized]['total_weight'] += weight
        votes[normalized]['voters'].append(parser_name)
        votes[normalized]['raw_titles'].add(cleaned)

    return dict(votes)


def select_winning_title(votes: Dict[str, Dict[str, Any]]) -> Tuple[str, str]:
    """
    Select the winning title from vote results.

    Returns both the normalized winning title (for confidence calculation)
    and the best surface form to display to the user.

    Args:
        votes: Vote dictionary from compute_title_votes()

    Returns:
        (final_title, winning_norm_title) tuple
    """
    if not votes:
        return ("", "")

    # Find the normalized title with the most weighted support
    winning_norm_title = max(votes.keys(), key=lambda k: votes[k]['total_weight'])

    # Pick the best surface form from that cluster
    # Prefer the form from the highest-trust parser that voted for it
    winning_data = votes[winning_norm_title]

    # Find the highest-trust voter
    best_voter = max(
        winning_data['voters'],
        key=lambda parser: PARSER_TRUST.get(parser, 0.3)
    )

    # Ideally we'd track which parser produced which raw title, but we don't
    # So just pick one of the raw titles (they should be very similar)
    # Prefer titles with proper capitalization (more uppercase letters)
    raw_titles = list(winning_data['raw_titles'])
    if raw_titles:
        # Prefer titles that look properly capitalized
        # (simple heuristic: more uppercase letters = more likely proper case)
        final_title = max(raw_titles, key=lambda t: sum(1 for c in t if c.isupper()))
    else:
        final_title = winning_norm_title

    return (final_title, winning_norm_title)


def compute_title_confidence(
    votes: Dict[str, Dict[str, Any]],
    winning_norm_title: str,
    parse_results: List[ParseResult]
) -> float:
    """
    Compute confidence score for the winning title.

    Confidence is based on:
    1. Support ratio: weighted support for winner vs total weight cast
    2. Top-tier coverage: did our strongest parsers agree?
    3. Parser diversity: how many distinct parsers agreed?

    Args:
        votes: Vote dictionary from compute_title_votes()
        winning_norm_title: The normalized title that won
        parse_results: Original list of parser results (for context)

    Returns:
        Confidence score in [0.0, 1.0]
    """
    if not votes or not winning_norm_title or winning_norm_title not in votes:
        return 0.0

    winning_data = votes[winning_norm_title]

    # 1. Support ratio: how much weight supports the winner vs total weight
    total_weight = sum(v['total_weight'] for v in votes.values())
    if total_weight == 0:
        return 0.0

    support_weight = winning_data['total_weight']
    support_ratio = support_weight / total_weight

    # 2. Top-tier coverage: did strong parsers (trust >= 0.8) agree?
    # This prevents low confidence even if weak parsers all agree
    # Only consider high-trust parsers that actually participated in this run
    top_tier_voters = {
        result.parser_name
        for result in parse_results
        if result.title and PARSER_TRUST.get(result.parser_name, 0.3) >= 0.8
    }
    top_tier_total = sum(
        PARSER_TRUST.get(name, 0.3)
        for name in top_tier_voters
    )

    if top_tier_total > 0:
        top_tier_support = sum(
            PARSER_TRUST.get(voter, 0.3)
            for voter in winning_data['voters']
            if voter in top_tier_voters
        )
        top_tier_ratio = top_tier_support / top_tier_total
    else:
        # No top-tier parsers available, rely more on support ratio
        top_tier_ratio = support_ratio

    # 3. Parser diversity: penalize if only one parser found anything
    num_distinct_voters = len(set(winning_data['voters']))
    parser_diversity_factor = min(1.0, num_distinct_voters / 2.0)
    # 1 parser -> 0.5, 2+ parsers -> 1.0

    # Fuse the three factors
    base_confidence = (support_ratio * 0.6) + (top_tier_ratio * 0.4)
    title_confidence = base_confidence * parser_diversity_factor

    # Clamp to valid range
    return max(0.0, min(1.0, title_confidence))


def bucket_confidence_level(confidence: float) -> ConfidenceLevel:
    """
    Convert numeric confidence to ConfidenceLevel enum.

    Thresholds:
    - HIGH: >= 0.85
    - MEDIUM: >= 0.65
    - LOW: >= 0.4
    - VERY_LOW: < 0.4

    Args:
        confidence: Numeric confidence score

    Returns:
        ConfidenceLevel enum
    """
    if confidence >= 0.85:
        return ConfidenceLevel.HIGH
    elif confidence >= 0.65:
        return ConfidenceLevel.MEDIUM
    elif confidence >= 0.4:
        return ConfidenceLevel.LOW
    else:
        return ConfidenceLevel.VERY_LOW


def build_title_and_confidence(
    parse_results: List[ParseResult]
) -> Tuple[str, float, ConfidenceLevel, Dict[str, Any]]:
    """
    Main entry point: compute consensus title and confidence from parser results.

    This is the function that TorrentContentDetector.identify() should call
    to get the final title and confidence based purely on parser agreement.

    Args:
        parse_results: List of all parser results

    Returns:
        (final_title, title_confidence, confidence_level, metadata) tuple where:
        - final_title: The consensus title string
        - title_confidence: Numeric confidence score (0-1)
        - confidence_level: ConfidenceLevel enum
        - metadata: Dict with voting details for debugging
    """
    # Edge case: no results at all
    if not parse_results:
        return ("Unknown", 0.0, ConfidenceLevel.VERY_LOW, {
            'error': 'No parser results available'
        })

    # Build vote table
    votes = compute_title_votes(parse_results)

    # Edge case: no parser extracted any title
    if not votes:
        return ("Unknown", 0.0, ConfidenceLevel.VERY_LOW, {
            'error': 'No parsers extracted a title'
        })

    # Select winning title
    final_title, winning_norm_title = select_winning_title(votes)

    # Compute confidence
    title_confidence = compute_title_confidence(votes, winning_norm_title, parse_results)

    # Bucket to enum
    confidence_level = bucket_confidence_level(title_confidence)

    # Build metadata for debugging
    metadata = {
        'score': title_confidence,
        'level': confidence_level.name,
        'voting': {
            'votes': [
                {
                    'normalized_title': norm_title,
                    'total_weight': data['total_weight'],
                    'voters': data['voters'],
                    'examples': list(data['raw_titles'])[:3],
                }
                for norm_title, data in votes.items()
            ],
            'chosen_normalized_title': winning_norm_title,
        }
    }

    return (final_title, title_confidence, confidence_level, metadata)
