# LibQuery Validation Report

## Performance Results

| Metric | Result |
|--------|--------|
| Full pipeline (all 6 libraries, download + ingest) | ~45 seconds |
| Bible ingest (66 books, PyArrow -> Parquet) | ~3 seconds |
| Single verse query (warm Spark session) | ~2 seconds |
| Parquet compression vs raw JSON (Snappy) | 4:1 size reduction |
| HDFS block size | 8MB |
| HDFS replication factor | 3 |


The 45-second total download time is dominated by API rate limiting across six external sources. Local processing (ingest + write) is a small fraction of that time.

---

## Completeness Checks

The `ls` command reports per-library download counts against known totals:

```
bible:        66/66    downloaded
quran:      114/114    downloaded
talmud:       37/37    downloaded
mormon:       15/15   downloaded
hindu:         7/7     downloaded
shakespeare:  37/37    downloaded
```

`Library.validate_files()` is called at the start of every ingest run and raises `FileNotFoundError` immediately if expected raw files are missing, preventing partial or corrupt Parquet writes.

---

## Accuracy :  Spot-Check Validations

Each entry below was queried via `libquery` and verified against its source API or authoritative text.

| Library | Query | Expected first line | Result |
|--------|-------|-------------------|--------|
| Bible | `libquery bible genesis 1:1` | In the beginning God created the heaven and the earth. | Correct |
| Quran | `libquery quran 3:2` | GOD - there is no deity save Him, the Ever-Living, the Self-Subsistent Fount of All Being! | Correct |
| Talmud | `libquery talmud berakhot 2a` | The beginning of tractate Berakhot, the first tractate in the first of the six orders of Mishna, | Correct |
| Mormon | `libquery mormon 1nephi 1:1` | I, Nephi, having been born of goodly parents... | Correct |
| Hindu | `libquery hindu bhagavadgita 2:47` | Thy right is to work only, but never with its fruits... | Correct |
| Shakespeare | `libquery shakespeare hamlet 1:1` | BERNARDO: Who's there? FRANCISCO: Nay, answer me: stand, and unfold yourself.| Correct |

---

## Schema Conformance

All Parquet files enforce the following schema via PyArrow at write time:

```
library  : string (not null)
book     : string (not null)
chapter  : int32  (not null)
verse    : int32  (not null)
text     : string (not null)
lang     : string (not null)
```

Records with empty or whitespace-only `text` fields are filtered in `engine.py` before results are returned. No null `text` values are present in any Parquet file.

---

## Edge Case Behavior

| Scenario | Behavior |
|----------|----------|
| Unknown library name (`libquery ls talmus`) | `[registry] Unknown library 'talmus'. Available: bible, quran, ...` - no crash |
| Book not downloaded | `[router] ERROR: No data for {library}/{book}. Run: libquery download ...` |
| API failure during download | Per-book `RequestException` caught, logged, skipped and remaining books continue |
| Null/empty text segments (Talmud, Hindu APIs) | Filtered at parse time in `Library.parse()` so not written to Parquet |
| Duplicate download attempt | `is_downloaded()` check returns early with "already downloaded" message |
| Malformed reference string | C parser returns error before payload is sent to server |
| Server not running | `[Client] Error: Cannot connect to LibQuery server at {host}:{port}. Start it with: libquery host` |
| Invalid SQL input (injection attempt) | `_safe()` in `sql_builder.py` validates against `[a-z0-9_\-]{1,64}` whitelist and raises `ValueError` |
| Privileged command without token | Server rejects `close`/`restart` without valid admin token |
| Java not found on startup | Server prints install link and exits before Spark initialization |
| Multi-surah Quran query | `_load_books()` unions all surahs in range into single DataFrame |
| Concurrent queries | UUID-named temp views prevent collisions |

---

## Data Quality Metrics

| Metric | Value |
|--------|-------|
| Null rate across all text fields | 0% (filtered at ingest) |
| Schema violations | 0 (PyArrow enforces at write time) |
| Books with verse number errors | 0 (all libraries verified post-fix) |
| HTML artifacts in Shakespeare and Talmud text | 0 (`_strip_html()` applied at parse time) |

---

## Known Limitations

- **Query latency includes JVM warm-up on first query** : the SparkSession takes 5–10 seconds to initialize on server startup. All subsequent queries run at ~2 seconds.
- **Shakespeare text is line-based, not verse-based** : the `verse` field for Shakespeare maps to line index within a scene rather than a traditional verse number. Cross-scene range queries are supported but may return large result sets.
- **Rate limiting on full download** : the 45-second full pipeline time is entirely API rate limiting. Individual library downloads are faster: Bible ~3 seconds ingest, others vary by API response time.
- **HDFS requires local Hadoop installation** : Windows users must place `winutils.exe` and `hadoop.dll` in `hadoop\bin\` per the README.
