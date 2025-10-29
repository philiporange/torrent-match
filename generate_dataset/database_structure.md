# Database Structure Documentation

This document describes the structure of the `test.sqlite` database, which appears to be a torrent tracking database with YTS (YIFY) movie data integration.

## Database Overview

The database contains 8 tables with approximately 38 million file records and 8.5 million torrent records, indicating this is a large-scale torrent indexing system.

## Table Descriptions

### 1. categories
**Purpose**: Stores torrent categories for classification
**Row Count**: 50

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT, NOT NULL | Unique identifier for each category |
| name | TEXT | UNIQUE | Category name (e.g., "Audio", "Audio: Music", "Audio: Audio books") |

**Indexes**:
- `IDX_8b0be371d28245da6e4f4b6187` on `name` column

**Sample Data**:
```
100|Audio
101|Audio: Music
102|Audio: Audio books
103|Audio: Sound clips
104|Audio: FLAC
```

### 2. torrents
**Purpose**: Main table storing torrent metadata and information
**Row Count**: 8,569,954

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, NOT NULL | Unique torrent identifier |
| category | INTEGER | NOT NULL, FOREIGN KEY → categories.id | Category ID reference |
| status | TEXT | NOT NULL | Torrent status (e.g., "member") |
| name | TEXT | NOT NULL | Torrent name/title |
| numFiles | INTEGER | NOT NULL | Number of files in the torrent |
| size | FLOAT | NOT NULL | Total size in bytes |
| seeders | INTEGER | NOT NULL | Number of seeders |
| leechers | INTEGER | NOT NULL | Number of leechers |
| username | TEXT | NOT NULL | Uploader username |
| added | INTEGER | NOT NULL | Unix timestamp when added |
| description | TEXT | | Optional description |
| imdb | TEXT | | IMDB identifier |
| language | TEXT | | Content language |
| textLanguage | TEXT | | Text language |
| infoHash | TEXT | NOT NULL | Torrent info hash |

**Indexes**: Multiple indexes on frequently queried columns (category, numFiles, size, seeders, leechers, username, added, imdb, language, textLanguage)

**Sample Data**:
```
3211594|205|member|High.Chaparall.S02E02.PDTV.XViD.SWEDiSH-HuBBaTiX|28|375299009.0|1|0|kbdcb|1080252480|Andra avsnittet på säsong två av High Chaparall.||||B03C8641415D3A0FC7077F5BF567634442989A74
3211609|201|member|School.Of.Rock.PROPER.DVDRip.XviD-DMT|53|739308799.0|0|0|Chippen|1080290117|OrginalRelease||||A896F7155237FB27E2EAA06033B5796D7AE84A1D
```

### 3. files
**Purpose**: Stores individual file information within torrents
**Row Count**: 38,012,759

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT, NOT NULL | Unique file identifier |
| name | TEXT | | File name with extension |
| size | FLOAT | NOT NULL | File size in bytes |
| parentTorrentId | INTEGER | NOT NULL, FOREIGN KEY → torrents.id | Reference to parent torrent |

**Indexes**:
- `IDX_332d10755187ac3c580e21fbc0` on `name`
- `IDX_eb822d74e27a05d7fd95d73799` on `parentTorrentId`

**Sample Data**:
```
1|Sword Art Online II - 15 Corrigido [1080p].mkv|566203848.0|11671640
2|Friends Forever #13.cbz|61380450.0|11671642
3|12.Monkeys.S01E03.720p.HDTV.x264-KILLERS.mkv|1123546046.0|11671643
```

### 4. yts_movies
**Purpose**: Stores YTS (YIFY) movie metadata
**Row Count**: 59,486

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, NOT NULL | Unique movie identifier |
| name | TEXT | NOT NULL | Movie title with year |
| description | TEXT | | Movie plot summary |
| imdb | TEXT | | IMDB identifier (tt format) |
| language | TEXT | | Movie language code |

**Sample Data**:
```
1|Bikini Model Academy (2015)|When T. J. and Benji, two California twenty-something best buddies, lose their girlfriends, they start a home grown bikini modeling academy to make money and meet new girls. With a little help from T.J.'s Uncle Seymour (Gary Busey), the guys begin recruiting pretty girls, until a rival modeling school owned by their old grade school enemy tries to shut them down. —joshishivansh|tt3208802|en
2|+1 (2013)|Three college friends hit the biggest party of the year, where a mysterious phenomenon disrupts the night, quickly descending into a chaos that challenges their friendships - and whether they can stay alive.|tt2395385|en
```

### 5. yts_torrent_data
**Purpose**: Stores torrent-specific data for YTS movies
**Row Count**: 120,444

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT, NOT NULL | Unique identifier |
| quality | TEXT | NOT NULL | Video quality (720p, 1080p, etc.) |
| size | FLOAT | NOT NULL | Torrent size in bytes |
| seeders | INTEGER | NOT NULL | Number of seeders |
| uploadedUnix | INTEGER | NOT NULL | Upload timestamp (Unix) |
| infoHash | TEXT | NOT NULL | Torrent info hash |
| parentYtsId | INTEGER | NOT NULL, FOREIGN KEY → yts_movies.id | Reference to parent YTS movie |

**Indexes**:
- `IDX_b511e3dfdbb002bc5a6edc95c4` on `parentYtsId`
- `IDX_d327291653f0844751d4d0dc02` on `infoHash`

**Sample Data**:
```
1|720p|735156634.0|5|1446306051|80F67E2D236A1A2854876F6A409C92D2D54C3849|1
2|1080p|1331439862.0|1|1446306056|BA2DD0FB35E9055372873D420E5C951CD41D6A8F|1
3|720p|788267008.0|0|1446306938|5CAAF4D2A62FB12AF7A5EDA177686B5F97EDA162|2
```

### 6. migrations
**Purpose**: Database migration tracking
**Row Count**: 3

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT, NOT NULL | Migration ID |
| timestamp | BIGINT | NOT NULL | Migration timestamp |
| name | VARCHAR | NOT NULL | Migration name |

**Sample Data**:
```
1|1616989903708|initialStructure1616989903708
2|1616989944537|addFails1616989944537
4|1631138527819|addYts1631138527819
```

### 7. db_data
**Purpose**: Key-value storage for application data
**Row Count**: 1

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY, NOT NULL | Data key |
| jsonVal | TEXT | NOT NULL | JSON value |

**Sample Data**:
```
lastYtsPage|1219
```

### 8. missed
**Purpose**: Tracks missed operations/failed attempts
**Row Count**: 0

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, NOT NULL | Unique identifier |
| count | INTEGER | DEFAULT 0 | Miss count |

## Relationships

1. **categories → torrents**: One-to-many relationship via `category` field
2. **torrents → files**: One-to-many relationship via `parentTorrentId` field
3. **yts_movies → yts_torrent_data**: One-to-many relationship via `parentYtsId` field

## Key Observations

- This is a large-scale torrent database with millions of records
- The database tracks both general torrents and specialized YTS movie torrents
- File sizes are stored as floating point numbers (likely in bytes)
- Timestamps use Unix epoch format
- The database includes proper indexing for performance optimization
- IMDB integration suggests movie/media focus
- Multiple language support for internationalization
- The `missed` table appears to be unused (0 rows)
- Migration tracking indicates the database has evolved over time