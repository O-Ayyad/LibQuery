# LibQuery

LibQuery is a lightweight CLI for querying sacred texts and literature from the command line. A C frontend communicates with a local Python/Spark server over TCP. Text data is downloaded from public APIs, stored as Parquet files, and queried with SQL via Apache Spark.

```
libquery bible john 3:16
libquery quran 2:255
libquery hindu bhagavadgita 7:18
libquery talmud berakhot 2:1
libquery mormon 1nephi 1:1-3
```

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Reference Syntax](#reference-syntax)
- [Commands](#commands)
  - [Querying](#querying)
  - [Downloading](#downloading)
  - [Server Management](#server-management)
  - [Aliases](#aliases)
  - [Networking](#networking)
  - [Listing Libraries](#listing-libraries)
- [Supported Libraries](#supported-libraries)
  - [Bible](#bible)
  - [Quran](#quran)
  - [Talmud](#talmud)
  - [Hindu Texts](#hindu-texts)
  - [Book of Mormon](#book-of-mormon)
- [Aliases Reference](#aliases-reference)
- [Remote Server Usage](#remote-server-usage)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Data Sources](#data-sources)
- [Windows Setup Notes](#windows-setup-notes)

---

## Requirements

- **GCC** (or compatible C compiler)
- **Python 3.11+**
- **Java 17** (required by Apache Spark. See [Windows Setup Notes](#windows-setup-notes))
- **Windows only:** `winutils.exe` from [cdarlint/winutils](https://github.com/cdarlint/winutils)

---

## Installation

**1. Clone the repository**
```bash
git clone <repo-url>
cd libquery
```

**2. Install Python dependencies**
```bash
pip install -r requirements.txt
```

**3. Build the C frontend**
```bash
make
```
Or manually:
```bash
# Linux/macOS
gcc -Wall -Wextra -O2 -Isrc/c src/c/main.c src/c/parser.c -o libquery

# Windows
gcc -Wall -Wextra -O2 -Isrc/c src/c/main.c src/c/parser.c -o libquery.exe -lws2_32
```


## Install Hadoop

A full install of Hadoop is required. (Windows requires addional confinguration. See [Windows Setup Notes](#windows-setup-notes))

https://hadoop.apache.org/releases.html


**5. Add `libquery` to your PATH** so it can be run from any directory.

---

## Quick Start

```bash
# Start the server (opens in a new terminal window)
libquery host

# Download some texts
libquery download bible genesis
libquery download quran
libquery download talmud berakhot
libquery download mormon 1nephi

# Query
libquery bible genesis 1
libquery bible john 3:16
libquery quran 2:255
libquery talmud berakhot 2:1
libquery mormon 1nephi 1
```

---

## Reference Syntax

References are used after the book name to specify what to retrieve.

| Syntax      | Meaning                                    | Example                        |
|-------------|-------------------------------------------|--------------------------------|
| *(none)*    | Entire book                               | `libquery bible mark`          |
| `N`         | Whole chapter N                           | `libquery bible mark 4`        |
| `N:V`       | Single verse                              | `libquery bible john 3:16`     |
| `N-M`       | Chapters N through M                      | `libquery bible mark 1-3`      |
| `N:V-M`     | N:V through end of chapter M             | `libquery bible mark 4:1-6`    |
| `N-M:V`     | Start of chapter N through M:V           | `libquery bible mark 1-3:5`    |
| `N:V-M:W`   | N:V through M:W                           | `libquery bible mark 4:1-4:12` |

**Quran** uses a different layout since it is a single-book library. The surah number takes the place of the book argument:

```bash
libquery quran 2           # Entire surah 2
libquery quran 2:255       # Surah 2, ayah 255
libquery quran 2:1-10      # Surah 2, ayahs 1–10
libquery quran 2:1-3:10    # Surah 2:1 through Surah 3:10
```

---

## Commands

### Querying

```bash
libquery <library> <book> [ref]
```

Query a book, optionally scoped to a reference. Results are printed to stdout with `chapter:verse` prefixes.

```bash
libquery bible genesis 1:1
libquery bible psalms 23
libquery quran 2:255
libquery talmud berakhot 2:1
libquery hindu bhagavadgita 2
libquery hindu ramayana-1 1:1
libquery mormon 1nephi 3:7
```

---

### Downloading

```bash
libquery download <library> [book]
```

Downloads and ingests text data from external APIs into local Parquet storage. Data persists between server restarts so you only need to download once.

```bash
# Download a single book
libquery download bible genesis
libquery download talmud berakhot
libquery download mormon 1nephi
libquery download hindu bhagavadgita
libquery download hindu ramayana-1

# Download an entire library
libquery download bible
libquery download quran
libquery download talmud
libquery download hindu
libquery download mormon

# Download everything (prompts for confirmation)
libquery download all
```

If a book is already downloaded then it will be skipped automatically.

---

### Server Management

The server must be running to process queries and downloads. It runs as a separate terminal window.

```bash
libquery host       # Start the server
libquery ping       # Check if the server is online
libquery close      # Stop the server
libquery restart    # Stop and restart the server
```

The server starts automatically with `libquery host` and listens on port **9237**. It initialises Apache Spark on startup which may take 10–20 seconds.

---

### Aliases

Aliases let you create short names for libraries and books. They are resolved locally without contacting the server.

```bash
# Add an alias
libquery alias add bible b
libquery alias add genesis g
libquery alias add quran q

# Use aliases
libquery b g 1:1        # → libquery bible genesis 1:1
libquery q 2:255        # → libquery quran 2:255

# List all user-defined aliases
libquery alias ls

# Remove an alias
libquery alias rm b

# Remove all aliases
libquery alias rm all
```

Aliases can be chained and both library and book can be aliased independently.

**Built-in aliases** (cannot be overwritten):

| Alias | Resolves to |
|-------|------------|
| `psalm` / `psalms` | `psalms` |
| `song` / `solomon` / `songofsolomon` | `songofsongs` |
| `1stjohn` | `1john` |
| `2ndjohn` | `2john` |
| `3rdjohn` | `3john` |
| `1stsamuel` | `1samuel` |
| `2ndsamuel` | `2samuel` |
| `1stkings` / `2ndkings` | `1kings` / `2kings` |
| `bhagavad-gita` / `bhagavad_gita` | `bhagavadgita` |
| `bala` / `balakanda` | `ramayana-1` |
| `ayodhya` / `ayodhyakanda` | `ramayana-2` |
| `aranya` / `aranyakanda` | `ramayana-3` |
| `kishkindha` / `kishkindhakanda` | `ramayana-4` |
| `sundara` / `sundar` / `sundarakanda` | `ramayana-5` |
| `yuddha` / `yuddhakanda` | `ramayana-6` |
| `ramayana` | `ramayana-1` (Bala Kanda) |

---

### Networking

By default, LibQuery connects to `127.0.0.1` (localhost). You can point it to a remote server running LibQuery on another machine on your network.

```bash
libquery target                  # Show current target IP
libquery target 192.168.1.100    # Route queries to a remote server
libquery target local            # Reset to localhost
libquery target rm               # Remove target IP, revert to localhost
libquery target help             # Show target usage
```

When a target IP is set all queries and downloads are sent to that server. Server management commands (`host`, `close`, `restart`) always operate on the local machine.

---

### Listing Libraries

```bash
libquery ls                 # List all libraries with download counts
libquery ls bible           # List all books in the Bible with YES/NO download status
libquery ls talmud          # List all Talmud tractates with download status
```

---

## Supported Libraries

### Bible

**66 books** : King James Version (KJV)

Books are referenced by lowercase name with no spaces:

```bash
libquery bible genesis 1:1
libquery bible songofsongs 1
libquery bible 1corinthians 13
libquery bible revelation 22
```

All 66 protestant canonical books of the Old and New Testament are supported.

---

### Quran

**114 surahs** : Arabic text (Uthmani) + English translation (Muhammad Asad)

The Quran uses a different query syntax. The surah number replaces the book argument:

```bash
libquery quran 1            # Al-Fatihah (entire surah)
libquery quran 2:255        # Ayat al-Kursi
libquery quran 36           # Yaseen (entire surah)
```

Both Arabic and English are returned for each verse with Arabic displayed first.

---

### Talmud

**37 tractates** : Babylonian Talmud with English translation (Sefaria / William Davidson)

```bash
libquery talmud berakhot
libquery talmud berakhot 2:1
libquery talmud sanhedrin 4
libquery talmud bava-kamma 1
```

Chapter numbers correspond to daf (folio) numbers. Tractates with hyphens must be typed exactly.

Both Hebrew and English are returned for each verse with Hebrew displayed first.

---

### Hindu Texts

**7 books** : Sanskrit originals with English translations

#### Bhagavad Gita

18 chapters, Sanskrit + English (Swami Sivananda translation):

```bash
libquery hindu bhagavadgita         # Entire Gita
libquery hindu bhagavadgita 2       # Chapter 2 
libquery hindu bhagavadgita 2:12    
```

#### Valmiki Ramayana

6 kandas (books), Sanskrit + English. Each "kanda" is queried separately:
 
```bash
libquery hindu ramayana-1           # Entire Bala Kanda
libquery hindu bala 1:1             # First verse (using alias)
libquery hindu sundara 1            # Sundara Kanda chapter 1
libquery hindu ramayana-6 131       # Final chapter of Yuddha Kanda
```

Chapter = sarga (section), verse = sloka number within that sarga.

---

### Book of Mormon

**15 books** : English

```bash
libquery mormon 1nephi
libquery mormon 1nephi 3:7
libquery mormon alma 32
libquery mormon moroni 10
```

---

## Remote Server Usage

LibQuery supports a client/server model where one machine hosts the server and others query it over the network.

**On the server machine:**
```bash
libquery host
```

**On client machines:**
```bash
libquery target 192.168.1.100    # Point to the server's IP
libquery bible genesis 1         # Queries run on the remote server
```

The server listens on port **9237**. Make sure this port is open on the server's firewall.

Downloads initiated from a client machine run on the server. Data is stored and served from the server only.

To reset to local:
```bash
libquery target rm               # Removes current target and defaults to local
libquery target local            # Point to localhost 127.0.0.1
```

---

## Project Structure

```
libquery/
├── Makefile
├── requirements.txt
├── src/
│   ├── c/
│   │   ├── main.c                CLI entry point, socket client, command dispatch
│   │   ├── parser.c              Reference string parser (1:5, 2-3:19, etc.)
│   │   └── parser_funcs.h        Shared types: Position, Range
│   └── python/
│       ├── config/
│       │   └── settings.py       Server host/port, paths, API URLs
│       ├── ingestion/
│       │   ├── fetch.py          Downloads raw data from external APIs
│       │   └── ingest.py         Parses raw JSON/CSV to Parquet via PyArrow
│       ├── local/
│       │   ├── alias_handler.py  Alias CRUD : runs locally, no server needed
│       │   └── network_handler.py  Target IP config : runs locally
│       ├── networking/
│       │   ├── server.py         Async TCP server (asyncio), admin token, Spark init
│       │   ├── router.py         Routes JSON payloads to engine or ingestion
│       │   └── registry.py       Tracks which books are downloaded on disk
│       └── query/
│           ├── engine.py         Spark session, loads Parquet, runs SQL
│           └── sql_builder.py    Builds SQL WHERE clauses from range parameters
└── data/
    ├── raw/                      Downloaded JSON/CSV (temporary, cleaned after ingest)
    ├── parquet/                  Processed Parquet files : the actual database
    │   ├── bible/genesis/
    │   ├── quran/al-baqara/
    │   ├── talmud/berakhot/
    │   ├── hindu/bhagavadgita/
    │   └── mormon/1nephi/
    ├── serverdata/               Runtime files 
    └── userdata/                 User config (aliases.json, networking_config.json)
```

---

## Architecture

```
libquery <args>
    │
    ├── Local commands (no server needed):
    │   alias_handler.py     alias add/rm/ls/resolve
    │   network_handler.py   target get/set
    │
    └── Server commands (TCP to port 9237):
            │
            ▼
        server.py  (asyncio TCP server)
            │
            ▼
        router.py  (JSON payload dispatch)
            │
            ├── cmd: query  → engine.py → sql_builder.py → Spark SQL → Parquet
            ├── cmd: download → fetch.py → ingest.py → Parquet
            ├── cmd: ping   → "Server is online on port: 9237"
            ├── cmd: ls     → registry.py → book/download status
            └── cmd: close  → graceful shutdown (token-authenticated)
```

**Data flow for a query:**
1. `main.c` builds a JSON payload and sends it over TCP to port 9237
2. `router.py` receives and dispatches to `engine.py`
3. `engine.py` loads the relevant Parquet directory as a Spark temp view
4. `sql_builder.py` generates a SQL WHERE clause from the chapter/verse range
5. Spark executes the query and returns rows
6. `router.py` formats results as `chapter:verse  text` lines
7. `main.c` receives the lines and prints them with word-wrapped formatting

**Data flow for a download:**
1. `fetch.py` downloads raw JSON or CSV from the external API
2. `ingest.py` parses it into normalised rows `(library, book, chapter, verse, text, lang)`
3. PyArrow writes the rows to a Parquet dataset at `data/parquet/<library>/<book>/`
4. Raw files are deleted after successful ingest
5. `registry.py` scans the disk on the next query to detect newly available books

---

## Data Sources

| Library | Source | Languages |
|---------|--------|-----------|
| Bible (KJV) | [getbible.net](https://api.getbible.net/v2/kjv) | English |
| Quran | [alquran.cloud](https://api.alquran.cloud/v1) | Arabic + English  |
| Talmud (Babylonian) | [Sefaria](https://www.sefaria.org/api/texts) | English + Hebrew |
| Bhagavad Gita | [DharmicData / bhavykhatri](https://github.com/bhavykhatri/DharmicData) | Sanskrit + English |
| Valmiki Ramayana | [imradhe/ramayanam-api](https://github.com/imradhe/ramayanam-api) | Sanskrit + English |
| Book of Mormon | [BraydenTW/book-of-mormon-api](https://github.com/BraydenTW/book-of-mormon-api) | English |

---

## Windows Setup Notes

### Java

Apache Spark requires Java 17. LibQuery automatically searches for it in common install locations (`C:\Program Files\Eclipse Adoptium`, `C:\Program Files\Microsoft`, etc.).

Download Java 17 from: https://adoptium.net/temurin/releases/?version=17

### Hadoop winutils

A full install of Hadoop is required and Windows requires additonal setup. Follow the guide below to install Hadoop:

https://gist.github.com/vorpal56/5e2b67b6be3a827b85ac82a63a5b3b2e


### Terminal and Unicode

For Arabic and Sanskrit text to display correctly, use **Windows Terminal** or **OpenConsole** rather than CMD, and run:
```
chcp 65001
```

CMD does not support right-to-left rendering or complex Unicode scripts. This cause الله to appear like هللا on the terminal. Arabic, Hebrew, and Devanagari will appear garbled in CMD but display correctly in Windows Terminal with a Unicode-capable font such as Cascadia Code or Noto Sans.

### Firewall

If using LibQuery in a client/server setup across a network then ensure port **9237** is open on the server machine's firewall. For queries from external networks you need to portforward. I did not test this functionality and I'm not sure if it works properly.
