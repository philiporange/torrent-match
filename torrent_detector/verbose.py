"""
Verbose logging utility for torrent content detector.

This module provides a centralized way to control debug output
throughout the application using a global verbose flag.
"""

import os
from typing import Optional

# Global verbose flag
_verbose = False

def set_verbose(verbose: bool) -> None:
    """Set the global verbose flag."""
    global _verbose
    _verbose = verbose

def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    return _verbose

def vprint(*args, **kwargs) -> None:
    """
    Print function that only outputs when verbose mode is enabled.

    This function has the same signature as print() and will only
    produce output when verbose mode is turned on via set_verbose().
    """
    if _verbose:
        print(*args, **kwargs)

def init_from_env() -> None:
    """Initialize verbose flag from environment variable."""
    # Check for VERBOSE environment variable
    verbose_env = os.getenv('VERBOSE', '').lower() in ('1', 'true', 'yes', 'on')
    set_verbose(verbose_env)