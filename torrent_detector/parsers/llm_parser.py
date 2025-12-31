"""
LLM parser implementation matching GuessIt's output format.

Fallback parser using language models for difficult cases.
Uses OpenAI's JSON mode for structured, reliable output with proper validation.

This parser:
- Outputs in GuessIt's format (screen_size, video_codec, release_group, type)
- Maps GuessIt-style fields to ParseResult format internally
- Explicitly requests JSON format in the prompt
- Uses response_format={"type": "json_object"} for both OpenAI and OpenRouter APIs
- Parses responses with json.loads() for safety (no eval())
- Validates all fields before creating ParseResult
- Handles edge cases like invalid media types and missing fields
"""

import json
from typing import Optional

import openai
import requests

from ..models import ParseResult, MediaType, TorrentContent
from ..verbose import vprint
from .base import Parser


class LLMParser(Parser):
    """Fallback parser using LLM for difficult cases with JSON mode"""

    def __init__(
        self,
        api_key: str,
        api_endpoint: str = "https://api.openai.com/v1",
        model: str = None,
    ):
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.is_openrouter = "openrouter.ai" in api_endpoint

        # Set default models based on service
        if model:
            self.model = model
        elif self.is_openrouter:
            self.model = "google/gemini-2.5-flash-latest"  # Default for OpenRouter
        else:
            self.model = "gpt-4.1-mini"  # Default for OpenAI (supports JSON mode)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def parse(self, name: str, content: TorrentContent) -> Optional[ParseResult]:
        if not self.is_available():
            return None

        try:
            prompt = self._build_prompt(name, content)

            if self.is_openrouter:
                # Use OpenRouter API
                result = self._call_openrouter_api(prompt)
            else:
                # Use OpenAI API with JSON mode
                result = self._call_openai_api(prompt)

            if not result:
                return None

            # Validate and extract fields
            return self._create_parse_result(result)

        except Exception as e:
            vprint(f"LLM parsing failed for '{name}': {e}")
            return None

    def _call_openai_api(self, prompt: str) -> Optional[dict]:
        """Call OpenAI API with JSON mode"""
        try:
            client = openai.OpenAI(api_key=self.api_key, base_url=self.api_endpoint)

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at parsing torrent names. You must respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},  # Enable JSON mode
                temperature=0.1,
                max_tokens=300,
            )

            result_text = response.choices[0].message.content.strip()
            return json.loads(result_text)

        except json.JSONDecodeError as e:
            vprint(f"Failed to parse JSON from OpenAI response: {e}")
            return None
        except Exception as e:
            vprint(f"OpenAI API error: {e}")
            return None

    def _call_openrouter_api(self, prompt: str) -> Optional[dict]:
        """Call OpenRouter API with JSON mode"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert at parsing torrent names. You must respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},  # Enable JSON mode
                "temperature": 0.1,
                "max_tokens": 300,
            }

            response = requests.post(
                f"{self.api_endpoint}/chat/completions",
                headers=headers,
                json=data,
                timeout=30,
            )

            if response.status_code == 200:
                result_text = response.json()["choices"][0]["message"][
                    "content"
                ].strip()
                return json.loads(result_text)
            else:
                vprint(
                    f"OpenRouter API error: {response.status_code} - {response.text}"
                )
                return None

        except json.JSONDecodeError as e:
            vprint(f"Failed to parse JSON from OpenRouter response: {e}")
            return None
        except Exception as e:
            vprint(f"OpenRouter API error: {e}")
            return None

    def _build_prompt(self, name: str, content: TorrentContent) -> str:
        """Build JSON-formatted prompt for LLM matching GuessIt's output format"""
        return f"""Parse the following torrent name and extract media information in the same format as GuessIt.

Torrent name: {name}
Number of video files: {content.movie_file_count}
Has season folders: {content.has_season_folders}
File structure indicates: {content.media_type.value}

Return a JSON object with the following fields (matching GuessIt's format):
- "title": string - The media title
- "year": integer or null - Release year if present
- "season": integer or null - Season number if TV show
- "episode": integer or null - Episode number if TV show
- "type": string - Either "movie" or "episode" (use "episode" for all TV content)
- "screen_size": string or null - Video resolution (e.g., "1080p", "720p", "2160p")
- "source": string or null - Source type (e.g., "Blu-ray", "WEB-DL", "HDTV", "WEBRip")
- "video_codec": string or null - Video codec (e.g., "H.264", "H.265", "x264", "x265")
- "release_group": string or null - Release group name

Focus on accuracy and matching GuessIt's vocabulary. Use null for fields you're unsure about.
Respond with ONLY the JSON object, no additional text."""

    def _create_parse_result(self, result: dict) -> Optional[ParseResult]:
        """Create ParseResult from validated JSON response with GuessIt-style field mapping"""
        try:
            # Validate required fields
            if not result.get("title"):
                vprint("LLM response missing required 'title' field")
                return None

            # Map GuessIt's "type" field to MediaType enum
            type_str = result.get("type", "").lower()
            if type_str == "movie":
                media_type = MediaType.MOVIE
            elif type_str in ["episode", "series"]:
                media_type = MediaType.TV_EPISODE  # Default to episode like GuessIt
            else:
                vprint(f"Invalid type '{type_str}', defaulting to UNKNOWN")
                media_type = MediaType.UNKNOWN

            return ParseResult(
                title=result.get("title"),
                year=result.get("year"),
                season=result.get("season"),
                episode=result.get("episode"),
                media_type=media_type,
                quality=result.get("screen_size"),  # Map GuessIt's screen_size to quality
                source=result.get("source"),
                codec=result.get("video_codec"),  # Map GuessIt's video_codec to codec
                group=result.get("release_group"),  # Map GuessIt's release_group to group
                parser_name="LLM",
                raw_data=result,
            )

        except Exception as e:
            vprint(f"Failed to create ParseResult from LLM response: {e}")
            return None
