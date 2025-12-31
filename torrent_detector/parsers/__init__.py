"""
Parser implementations for torrent content detection.

This package contains various parsers that extract media information from torrent names,
using different strategies and libraries for maximum coverage. Each parser is in its own
module for better organization and maintainability.
"""

from .base import Parser
from .guessit_parser import GuessItParser
from .ptn_parser import PTNParser
from .rebulk_parser import ReBulkParser
from .regex_parser import RegexParser
from .llm_parser import LLMParser


def create_parser_pipeline(
    include_llm: bool = False,
    llm_api_key: str = None,
    llm_api_endpoint: str = None,
    llm_model: str = None,
    parser_names: list = None
) -> list:
    """
    Create a list of parsers in order of preference.

    Args:
        include_llm: Whether to include LLM parser as fallback
        llm_api_key: LLM API key for LLM parser
        llm_api_endpoint: LLM API endpoint (OpenRouter or OpenAI)
        llm_model: LLM model to use
        parser_names: Optional list of parser names to use (e.g., ['guessit', 'ptn', 'llm']).
                     If None, uses all available parsers. Valid names:
                     'guessit', 'ptn', 'rebulk', 'regex', 'llm'

    Returns:
        List of parser instances
    """
    # Map of lowercase parser names to their classes
    parser_map = {
        'guessit': GuessItParser,
        'ptn': PTNParser,
        'rebulk': ReBulkParser,
        'regex': RegexParser,
    }

    parsers = []

    # If parser_names is specified, use only those parsers
    if parser_names is not None:
        # Normalize parser names to lowercase
        normalized_names = [name.lower().strip() for name in parser_names]

        # Add parsers in the order they appear in parser_names
        for name in normalized_names:
            if name == 'llm':
                # Handle LLM parser separately
                if llm_api_key:
                    if llm_api_endpoint is None:
                        llm_api_endpoint = "https://api.openai.com/v1"
                    llm_parser = LLMParser(llm_api_key, llm_api_endpoint, llm_model)
                    if llm_parser.is_available():
                        parsers.append(llm_parser)
            elif name in parser_map:
                parsers.append(parser_map[name]())
            else:
                # Unknown parser name, skip with a warning
                from ..verbose import vprint
                vprint(f"Warning: Unknown parser name '{name}', skipping")
    else:
        # Default behavior: add all parsers in order of preference
        parsers.append(GuessItParser())
        parsers.append(PTNParser())
        parsers.append(ReBulkParser())
        parsers.append(RegexParser())

        # Add LLM parser last if requested
        if include_llm and llm_api_key:
            if llm_api_endpoint is None:
                llm_api_endpoint = "https://api.openai.com/v1"

            llm_parser = LLMParser(llm_api_key, llm_api_endpoint, llm_model)
            if llm_parser.is_available():
                parsers.append(llm_parser)

    return parsers


__all__ = [
    'Parser',
    'GuessItParser',
    'PTNParser',
    'ReBulkParser',
    'RegexParser',
    'LLMParser',
    'create_parser_pipeline',
]
