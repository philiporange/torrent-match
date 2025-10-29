"""
Torrent file decoding utilities for torrent_match.

This module provides lightweight bencode decoding tailored specifically to
`.torrent` files so we can extract the declared torrent name and file layout
without adding external dependencies. The parsed result is represented as
`ParsedTorrent`, which exposes the torrent display name and a list of files
formatted with `path` and `length` keys for direct consumption by the
existing matching pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union


class TorrentFileParsingError(RuntimeError):
    """Raised when a torrent file cannot be decoded or is missing required fields."""


@dataclass(frozen=True)
class ParsedTorrent:
    """Container for decoded torrent file data."""

    name: str
    files: List[Dict[str, Any]]


def parse_torrent_file(torrent_path: Union[str, Path]) -> ParsedTorrent:
    """
    Parse a torrent file and extract its name and file listing.

    Args:
        torrent_path: Path to the `.torrent` file.

    Returns:
        ParsedTorrent containing the torrent display name and a list of file
        metadata dictionaries. Each dictionary contains at minimum `path` and
        `length` keys, which is the format expected by the matching pipeline.

    Raises:
        TorrentFileParsingError: If the file cannot be decoded or required
            fields are missing.
    """
    torrent_path = Path(torrent_path)
    if not torrent_path.exists():
        raise TorrentFileParsingError(f"Torrent file not found: {torrent_path}")

    raw_data = torrent_path.read_bytes()
    torrent_dict = _bdecode(raw_data)
    if not isinstance(torrent_dict, dict):
        raise TorrentFileParsingError("Torrent file does not contain a top-level dictionary.")

    info = torrent_dict.get("info")
    if not isinstance(info, dict):
        raise TorrentFileParsingError("Torrent file is missing required `info` dictionary.")

    name = _get_text_field(info, ("name.utf-8", "name"))
    if not name:
        raise TorrentFileParsingError("Torrent `info` dictionary missing `name` field.")

    files = _extract_files(info, name)
    if not files:
        raise TorrentFileParsingError("Torrent did not contain any file entries.")

    return ParsedTorrent(name=name, files=files)


def _extract_files(info_dict: Dict[str, Any], root_name: str) -> List[Dict[str, Any]]:
    """Extract file listings from the decoded info dictionary."""
    files_field = info_dict.get("files")
    if isinstance(files_field, list) and files_field:
        extracted = []
        for entry in files_field:
            if not isinstance(entry, dict):
                continue

            length = _get_int_field(entry, ("length", "size"))
            if length is None:
                continue

            path_components = _get_path_components(
                entry,
                ("path.utf-8", "path"),
            )

            if not path_components:
                continue

            # Build a path that matches how torrent clients materialize files.
            if path_components[0] == root_name:
                full_path = Path(*path_components)
            else:
                full_path = Path(root_name, *path_components)

            extracted.append(
                {
                    "path": str(full_path),
                    "length": length,
                }
            )
        return extracted

    # Single file torrent: use `name` and `length`.
    length = _get_int_field(info_dict, ("length",))
    if length is None:
        return []

    return [
        {
            "path": str(Path(root_name)),
            "length": length,
        }
    ]


def _get_text_field(source: Dict[str, Any], keys: Iterable[str]) -> str:
    """Return the first available textual field in `keys` decoded to UTF-8."""
    for key in keys:
        value = source.get(key)
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value.decode("utf-8", errors="replace")
        if isinstance(value, str):
            return value
    return ""


def _get_path_components(entry: Dict[str, Any], keys: Iterable[str]) -> List[str]:
    """Normalize the list of path components for a multi-file torrent entry."""
    for key in keys:
        components = entry.get(key)
        if isinstance(components, list):
            normalized: List[str] = []
            for part in components:
                if isinstance(part, (bytes, bytearray)):
                    normalized.append(part.decode("utf-8", errors="replace"))
                elif isinstance(part, str):
                    normalized.append(part)
            if normalized:
                return normalized
    return []


def _get_int_field(source: Dict[str, Any], keys: Iterable[str]) -> Union[int, None]:
    """Return the first integer-like value found among `keys`."""
    for key in keys:
        value = source.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, (bytes, bytearray)):
            try:
                return int(value)
            except ValueError:
                continue
    return None


def _bdecode(data: bytes) -> Any:
    """Minimal bencode decoder sufficient for `.torrent` metadata."""
    value, index = _decode_next(data, 0)
    if index != len(data):
        # Extra garbage at the end usually means malformed data.
        raise TorrentFileParsingError("Trailing data found after decoding torrent file.")
    return value


def _decode_next(data: bytes, index: int) -> Tuple[Any, int]:
    """Decode the next bencoded value starting at `index`."""
    if index >= len(data):
        raise TorrentFileParsingError("Unexpected end of data while decoding torrent file.")

    prefix = data[index:index + 1]
    if prefix == b"i":
        end = data.find(b"e", index)
        if end == -1:
            raise TorrentFileParsingError("Missing terminator for integer in torrent file.")
        number = data[index + 1:end]
        try:
            return int(number), end + 1
        except ValueError as exc:
            raise TorrentFileParsingError(f"Invalid integer value: {number!r}") from exc

    if prefix == b"l":
        items: List[Any] = []
        idx = index + 1
        while data[idx:idx + 1] != b"e":
            item, idx = _decode_next(data, idx)
            items.append(item)
        return items, idx + 1

    if prefix == b"d":
        dictionary: Dict[str, Any] = {}
        idx = index + 1
        while data[idx:idx + 1] != b"e":
            key_raw, idx = _decode_next(data, idx)
            key = _ensure_text_key(key_raw)
            value, idx = _decode_next(data, idx)
            dictionary[key] = value
        return dictionary, idx + 1

    if b"0" <= prefix <= b"9":
        colon = data.find(b":", index)
        if colon == -1:
            raise TorrentFileParsingError("String length delimiter missing in torrent file.")
        try:
            length = int(data[index:colon])
        except ValueError as exc:
            raise TorrentFileParsingError("Invalid string length in torrent file.") from exc
        start = colon + 1
        end = start + length
        if end > len(data):
            raise TorrentFileParsingError("String length exceeds torrent file size.")
        return data[start:end], end

    raise TorrentFileParsingError(f"Unknown bencode prefix: {prefix!r}")


def _ensure_text_key(key: Any) -> str:
    """Convert dictionary keys to UTF-8 strings."""
    if isinstance(key, str):
        return key
    if isinstance(key, (bytes, bytearray)):
        try:
            return key.decode("utf-8")
        except UnicodeDecodeError:
            return key.decode("utf-8", errors="replace")
    raise TorrentFileParsingError(f"Unsupported dictionary key type: {type(key)!r}")
