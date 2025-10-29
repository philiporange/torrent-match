"""
Abstract base class for torrent name parsers.

Defines the interface that all parser implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Optional

from ..models import ParseResult, TorrentContent


class Parser(ABC):
    """Abstract base class for parsers"""

    @abstractmethod
    def parse(self, name: str, content: TorrentContent) -> Optional[ParseResult]:
        """
        Parse torrent name and extract media information.

        Args:
            name: Torrent name to parse
            content: Analyzed torrent content information

        Returns:
            ParseResult with extracted information or None if parsing failed
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the parser's dependencies are available"""
        pass
