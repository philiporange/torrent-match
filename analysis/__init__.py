"""
Comprehensive analysis tools for torrent detector ensemble performance.

This package provides deep analysis of:
- Individual detector performance
- Detector agreement and consensus quality
- Ensemble effectiveness metrics
"""

from .individual_detector_analysis import DetectorPerformanceAnalyzer
from .detector_agreement_analysis import DetectorAgreementAnalyzer
from .run_analysis import UnifiedAnalysisRunner

__all__ = [
    'DetectorPerformanceAnalyzer',
    'DetectorAgreementAnalyzer',
    'UnifiedAnalysisRunner'
]

__version__ = '0.1.0'
__author__ = 'Philip Orange <git@philiporange.com>'
