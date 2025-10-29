"""
Peewee ORM bindings for the torrent database located at `/tmp/test/test.sqlite`.

Tables & key columns:
* categories – `id` (PK), `name` describing the torrent classification.
* torrents – `id` (PK), `category` → categories.id, `status`, `name`, `numFiles`,
  `size` (bytes), `seeders`, `leechers`, `username`, `added` (unix timestamp),
  optional `description`, `imdb`, `language`, `textLanguage`, `infoHash`.
* files – `id` (PK autoincrement), `name` (path), `size` (bytes), `parentTorrentId`
  → torrents.id.
* yts_movies – `id` (PK), `name`, optional `description`, `imdb`, `language`.
* yts_torrent_data – `id` (PK autoincrement), `quality`, `size` (bytes),
  `seeders`, `uploadedUnix` (unix timestamp), `infoHash`, `parentYtsId`
  → yts_movies.id.
* migrations – `id` (PK autoincrement), `timestamp` (bigint), `name`.
* db_data – `id` (PK text key), `jsonVal` (payload).
* missed – `id` (PK), `count` (default 0).

The module exposes a configurable SQLite database proxy alongside model
definitions that mirror the documented schema. Call `init_sqlite_database`
early in an application or script to connect the models to a concrete database
file (read-only or writable as required).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Optional, Union

from peewee import (
    BigIntegerField,
    AutoField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
    DatabaseProxy,
)


PathLike = Union[str, Path]

DB_DEFAULT_PATH = Path("/tmp/test/test.sqlite")
DEFAULT_PRAGMAS = {
    "journal_mode": "WAL",
    "foreign_keys": 1,
    "cache_size": -1024 * 64,
}

database_proxy: DatabaseProxy = DatabaseProxy()


def _build_database_uri(path: PathLike, read_only: bool) -> tuple[str, bool]:
    resolved = Path(path).resolve()
    if read_only:
        return f"file:{resolved.as_posix()}?mode=ro", True
    return resolved.as_posix(), False


def ensure_database_directory(path: PathLike) -> None:
    """
    Ensure the directory for the database file exists.

    Parameters
    ----------
    path:
        Filesystem path pointing at a SQLite database file.
    """
    resolved_path = Path(path).resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)


def init_sqlite_database(
    path: PathLike = DB_DEFAULT_PATH,
    *,
    read_only: bool = False,
    pragmas: Optional[Mapping[str, Union[str, int]]] = None,
) -> SqliteDatabase:
    """
    Instantiate and bind a SqliteDatabase to the shared proxy.

    Parameters
    ----------
    path:
        Filesystem path pointing at a SQLite database file.
        Default location is `/tmp/test/test.sqlite`.
    read_only:
        When True the connection uses a URI with `mode=ro` to prevent writes.
    pragmas:
        Optional pragma overrides merged with `DEFAULT_PRAGMAS`.
    """
    if not read_only:
        ensure_database_directory(path)

    uri, use_uri = _build_database_uri(path, read_only)
    pragma_dict: dict[str, Union[str, int]] = dict(DEFAULT_PRAGMAS)
    if pragmas:
        pragma_dict.update(pragmas)

    database = SqliteDatabase(uri, pragmas=pragma_dict, uri=use_uri)
    database_proxy.initialize(database)
    return database


class BaseModel(Model):
    """Shared base model configured to use the module-level database proxy."""

    class Meta:  # type: ignore[override]
        database = database_proxy


class Category(BaseModel):
    """Torrent classification buckets (e.g., video, audio, applications)."""

    id = IntegerField(primary_key=True)
    name = TextField(unique=True)

    class Meta:  # type: ignore[override]
        table_name = "categories"


class Torrent(BaseModel):
    """Primary torrent metadata including peers, size, and descriptive fields."""

    id = IntegerField(primary_key=True)
    category = ForeignKeyField(Category, backref="torrents", column_name="category")
    status = TextField()
    name = TextField()
    numFiles = IntegerField()
    size = FloatField()
    seeders = IntegerField()
    leechers = IntegerField()
    username = TextField()
    added = IntegerField()
    description = TextField(null=True)
    imdb = TextField(null=True)
    language = TextField(null=True)
    textLanguage = TextField(null=True)
    infoHash = TextField()

    class Meta:  # type: ignore[override]
        table_name = "torrents"


class File(BaseModel):
    """Individual files that belong to a torrent payload."""

    id = AutoField()
    name = TextField(null=True)
    size = FloatField()
    parentTorrent = ForeignKeyField(
        Torrent,
        backref="files",
        column_name="parentTorrentId",
        on_delete="CASCADE",
    )

    class Meta:  # type: ignore[override]
        table_name = "files"


class YtsMovie(BaseModel):
    """YTS movie catalogue entries with optional IMDB metadata."""

    id = IntegerField(primary_key=True)
    name = TextField()
    description = TextField(null=True)
    imdb = TextField(null=True)
    language = TextField(null=True)

    class Meta:  # type: ignore[override]
        table_name = "yts_movies"


class YtsTorrentData(BaseModel):
    """Torrent-level details associated with a YTS movie entry."""

    id = AutoField()
    quality = TextField()
    size = FloatField()
    seeders = IntegerField()
    uploadedUnix = IntegerField()
    infoHash = TextField()
    parentYts = ForeignKeyField(
        YtsMovie,
        backref="torrents",
        column_name="parentYtsId",
        on_delete="CASCADE",
    )

    class Meta:  # type: ignore[override]
        table_name = "yts_torrent_data"


class Migration(BaseModel):
    """Versioned migration log for schema evolution tracking."""

    id = AutoField()
    timestamp = BigIntegerField()
    name = TextField()

    class Meta:  # type: ignore[override]
        table_name = "migrations"


class DbData(BaseModel):
    """Key-value store used for miscellaneous persistent metadata."""

    id = TextField(primary_key=True)
    jsonVal = TextField()

    class Meta:  # type: ignore[override]
        table_name = "db_data"


class Missed(BaseModel):
    """Counter table that records missed operations or retries."""

    id = IntegerField(primary_key=True)
    count = IntegerField(default=0)

    class Meta:  # type: ignore[override]
        table_name = "missed"


__all__: Iterable[str] = (
    "Category",
    "Torrent",
    "File",
    "YtsMovie",
    "YtsTorrentData",
    "Migration",
    "DbData",
    "Missed",
    "init_sqlite_database",
    "ensure_database_directory",
    "database_proxy",
    "DB_DEFAULT_PATH",
)
