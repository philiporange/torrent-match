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


def create_parser_pipeline(include_llm: bool = False, llm_api_key: str = None, llm_api_endpoint: str = None, llm_model: str = None) -> list:
    """
    Create a list of parsers in order of preference.

    Args:
        include_llm: Whether to include LLM parser as fallback
        llm_api_key: LLM API key for LLM parser
        llm_api_endpoint: LLM API endpoint (OpenRouter or OpenAI)
        llm_model: LLM model to use

    Returns:
        List of parser instances
    """
    parsers = []

    # Add parsers in order of preference/skill
    parsers.append(GuessItParser())
    parsers.append(PTNParser())
    parsers.append(ReBulkParser())

    # Always add regex parser as basic fallback
    parsers.append(RegexParser())

    # Add LLM parser last if requested
    if include_llm and llm_api_key:
        if llm_api_endpoint is None:
            llm_api_endpoint = "https://api.openai.com/v1"  # Default to OpenAI

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
