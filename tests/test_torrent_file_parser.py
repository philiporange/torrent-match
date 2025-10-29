"""
Tests for the torrent file parser utilities.

These tests validate that `.torrent` metadata is decoded into structures that
the matching pipeline understands, covering both single-file and multi-file
torrents.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "torrent_match" / "torrent_file_parser.py"
SPEC = importlib.util.spec_from_file_location("torrent_file_parser", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Failed to load torrent_file_parser module for testing.")
torrent_file_parser = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = torrent_file_parser
SPEC.loader.exec_module(torrent_file_parser)

ParsedTorrent = torrent_file_parser.ParsedTorrent
TorrentFileParsingError = torrent_file_parser.TorrentFileParsingError
parse_torrent_file = torrent_file_parser.parse_torrent_file


def _bencode(value: Any) -> bytes:
    """Minimal encoder for the subset of bencode used in tests."""
    if isinstance(value, int):
        return b"i" + str(value).encode("ascii") + b"e"
    if isinstance(value, bytes):
        return str(len(value)).encode("ascii") + b":" + value
    if isinstance(value, str):
        data = value.encode("utf-8")
        return str(len(data)).encode("ascii") + b":" + data
    if isinstance(value, list):
        return b"l" + b"".join(_bencode(item) for item in value) + b"e"
    if isinstance(value, dict):
        # Keys must be sorted byte-wise.
        items = []
        for key in sorted(value.keys()):
            encoded_key = _bencode(key)
            encoded_value = _bencode(value[key])
            items.append(encoded_key + encoded_value)
        return b"d" + b"".join(items) + b"e"
    raise TypeError(f"Unsupported type for bencode: {type(value)}")


def _write_torrent(tmp_path: Path, name: str, payload: Dict[str, Any]) -> Path:
    torrent_path = tmp_path / name
    torrent_path.write_bytes(_bencode(payload))
    return torrent_path


def test_parse_single_file_torrent(tmp_path: Path) -> None:
    torrent_bytes = {
        "announce": "http://tracker.test",
        "info": {
            "name": "Example.mkv",
            "length": 1234,
            "piece length": 16384,
            "pieces": b"",
        },
    }
    torrent_path = _write_torrent(tmp_path, "single.torrent", torrent_bytes)

    parsed = parse_torrent_file(torrent_path)
    assert isinstance(parsed, ParsedTorrent)
    assert parsed.name == "Example.mkv"
    assert parsed.files == [{"path": "Example.mkv", "length": 1234}]


def test_parse_multi_file_torrent(tmp_path: Path) -> None:
    torrent_bytes = {
        "announce": "http://tracker.test",
        "info": {
            "name": "Show.Name.S01",
            "piece length": 16384,
            "pieces": b"",
            "files": [
                {
                    "path": ["Season 1", "Show.Name.S01E01.mkv"],
                    "length": 456,
                },
                {
                    "path": ["Season 1", "Show.Name.S01E02.mkv"],
                    "length": 789,
                },
            ],
        },
    }
    torrent_path = _write_torrent(tmp_path, "multi.torrent", torrent_bytes)

    parsed = parse_torrent_file(torrent_path)
    assert parsed.name == "Show.Name.S01"
    assert parsed.files == [
        {"path": "Show.Name.S01/Season 1/Show.Name.S01E01.mkv", "length": 456},
        {"path": "Show.Name.S01/Season 1/Show.Name.S01E02.mkv", "length": 789},
    ]


def test_invalid_torrent_raises(tmp_path: Path) -> None:
    bad_torrent = tmp_path / "bad.torrent"
    bad_torrent.write_text("not bencode", encoding="utf-8")

    with pytest.raises(TorrentFileParsingError):
        parse_torrent_file(bad_torrent)
