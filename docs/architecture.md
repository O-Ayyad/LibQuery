# LibQuery Architecture

## Overview

LibQuery is a distributed Big Data pipeline for querying literary and religious corpora from the command line. A C frontend communicates with a Python TCP server over a local or remote network connection. The server manages data acquisition, ingestion, and query execution using PyArrow, Apache Spark SQL, and HDFS.

---

## Stack

| Layer | Technology | Role |
|-------|-----------|------|
| CLI | C (GCC) | Reference parsing, TCP client, terminal rendering |
| Server | Python asyncio | Concurrent connection handling, request routing |
| Ingestion | PyArrow | JSON to Parquet transformation, schema enforcement |
| Query Engine | Apache Spark SQL | Catalyst optimizer, predicate pushdown, partition pruning |
| Storage Format | Apache Parquet (Snappy) | Columnar compressed storage |
|HDFS Interface |WebHDFS REST API |HTTP-based HDFS access. Server hosting on Windows machine|
| Distributed Store | HDFS | 8MB blocks, replication factor 3 |

---

## Component Map

```
libquery/
  src/
    c/
      main.c              CLI entry point, TCP client, print_verse() renderer
      parser.c            Reference string parser (1:5, 2-3:19, 1:1-2:10, ...)
      parser_funcs.h      Position/Range structs, LQ_MAX_PATH constants
    python/
      config/
        settings.py       HDFS paths, server port, API base URLs, corpus configs
	storage.py        File system and path detection
      ingestion/
        fetch.py          Per-library API downloaders with rate limiting and error handling
        ingest.py         Library definintion + Bible/Quran/Talmud/Mormon/Hindu/Shakespeare parsers
      networking/
        server.py         asyncio TCP server, Java check, Spark warm-up, admin token
        router.py         Payload routing, result formatting, bilingual display
        registry.py       Known/downloaded book tracking, filesystem cache
      query/
        engine.py         PySpark SQL executor, _load_books()
        sql_builder.py    SQL WHERE clause builder with injection guard
      local/
        alias_handler.py  add/rm/ls/resolve Runs locally, no server contact
        network_handler.py target IP get/set
  data/
    raw/          Temporary download location (deleted after ingest)
    parquet/      HDFS-backed persistent Parquet storage
    serverdata/   admin.token (gitignored)
    userdata/     aliases.json, target.json (gitignored)
    sample/       Small sample for testing without download
  docs/
    architecture.md
    data_dictionary.md
    validation.md
  hadoop/
    bin/          winutils.exe + hadoop.dll (Windows only, gitignored)
```

---

## Request Lifecycle

```
User types: libquery bible romans 1:19-2:5
                │
                ▼
         main.c - parser.c parses "1:19-2:5" into Position{1,19} → Position{2,5}
                │
                ▼
         Builds JSON payload:
         {"library":"bible","book":"romans","start_chapter":1,"start_verse":19,
          "end_chapter":2,"end_verse":5,"lang":"en"}
                │
         alias_handler.py resolve called on "bible" and "romans" first
                │
                ▼
         TCP connect -> server.py (asyncio, port from .env)
                │
                ▼
         router.py - routes to engine.execute(payload)
                │
                ▼
         engine.py:
           1. is_downloaded() pre-flight check
           2. _load_books() -> spark.read.parquet(hdfs://...parquet/bible/romans/)
           3. df.createTempView("libq_<uuid>")
           4. sql_builder.build_query() -> "SELECT chapter,verse,text,lang
                                           FROM libq_<uuid>
                                           WHERE (chapter=1 AND verse>=19)
                                              OR (chapter=2 AND verse<=5)
                                              AND lang='en'
                                           ORDER BY chapter, verse"
           5. spark.sql(sql).collect()
           6. dropTempView (finally block)
                │
                ▼
         router.py formats results as "chapter:verse text\n" lines
                │
                ▼
         TCP response streamed back to main.c
                │
                ▼
         print_verse() word-wraps and renders to terminal
```

---

## Server Startup Sequence

1. `configure_java()` : locate `JAVA_HOME`, exit with install link if not found
2. `_configure_hadoop()` : set Hadoop home for Windows winutils
3. `_get_spark()` : initialize `SparkSession` (warm-up, ~5–10s first time)
4. Generate admin token -> `data/serverdata/admin.token` (chmod 600)
5. `asyncio.start_server()` :begin accepting connections on configured port

---

## Networking

- **Local mode**: C frontend connects to `127.0.0.1:PORT`
- **Remote mode**: `libquery target <IP>` stores host in `data/userdata/target.json`; subsequent queries route to that IP
- **Concurrency**:  blocking Spark calls run in `ThreadPoolExecutor`
- **Security**: `close`/`restart` commands require SHA-256 admin token validation

---

## HDFS Layout

```
hdfs://namenode/
  libquery/
    bible/
      genesis/     *.parquet (Snappy, 8MB blocks, RF=3)
      exodus/
      ...          (66 books)
    quran/
      al-fatihah/
      al-baqarah/
      ...          (114 surahs)
    talmud/
      berakhot/
      ...          (37 tractates)
    mormon/
      1nephi/
      ...          (15 books)
    hindu/
      bhagavadgita/
      ...          (7 texts)
    shakespeare/
      hamlet/
      ...          (37 plays)
```

Spark reads use the per-book directory path, giving Catalyst partition pruning for free so a query for `bible/genesis` never touches `bible/exodus` or any other library directory.
