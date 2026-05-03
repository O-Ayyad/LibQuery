# LibQuery Data Dictionary

## Schema

All six libraries share a single unified schema enforced by PyArrow at write time.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `library` | `string` | No | Library identifier: `bible`, `quran`, `talmud`, `mormon`, `hindu`, `shakespeare` |
| `book` | `string` | No | Book/work within the library (see per-library tables below) |
| `chapter` | `int32` | No | Chapter, surah, daf, act, etc|
| `verse` | `int32` | No | Verse, ayah, amud, line index, etc|
| `text` | `string` | No | Plain text content. Empty strings filtered at ingest time. |
| `lang` | `string` | No | ISO 639-1 language code: `en` (English), `ar` (Arabic), `he` (Hebrew),`sa` (Sanskrit) |

---

## Per-Library Details

### Bible

- **Source**: `api.getbible.net/v2` (KJV translation)
- **Books**: 66 KJV canonical books
- **`chapter`**: Chapter number (1-indexed)
- **`verse`**: Verse number (1-indexed)
- **`lang`**: Always `en`
- **Books**: `genesis`, `exodus`, `leviticus`, `numbers`, `deuteronomy`, `joshua`, `judges`, `ruth`, `1samuel`, `2samuel`, `1kings`, `2kings`, `1chronicles`, `2chronicles`, `ezra`, `nehemiah`, `esther`, `job`, `psalms`, `proverbs`, `ecclesiastes`, `songofsolomon`, `isaiah`, `jeremiah`, `lamentations`, `ezekiel`, `daniel`, `hosea`, `joel`, `amos`, `obadiah`, `jonah`, `micah`, `nahum`, `habakkuk`, `zephaniah`, `haggai`, `zechariah`, `malachi`, `matthew`, `mark`, `luke`, `john`, `acts`, `romans`, `1corinthians`, `2corinthians`, `galatians`, `ephesians`, `philippians`, `colossians`, `1thessalonians`, `2thessalonians`, `1timothy`, `2timothy`, `titus`, `philemon`, `hebrews`, `james`, `1peter`, `2peter`, `1john`, `2john`, `3john`, `jude`, `revelation`

### Quran

- **Source**: `api.alquran.cloud` (Arabic: `ar.alafasy`; English: `en.asad`)
- **Books**: 114 surahs stored as individual books
- **`chapter`**: Surah number (1–114)
- **`verse`**: Ayah number (1-indexed)
- **`lang`**: `ar` (Arabic) and `en` (English)  both rows present per ayah
- **Book slugs**: Surah names in lowercase, e.g. `al-fatihah`, `al-baqarah`, ..., `an-nas`

### Talmud

- **Source**: `sefaria.org/api/texts`
- **Books**: 37 tractates
- **`chapter`**: Daf number (e.g. daf 2 = chapter 2)
- **`verse`**: Amud  `1` = amud aleph (a), `2` = amud bet (b). Rendered as `2a`/`2b` in the terminal.
- **`lang`**: `he` (Hebrew) and `en` (English)  both rows present per segment
- **Book slugs**: `berakhot`, `shabbat`, `eruvin`, `pesachim`, `yoma`, `sukkah`, `beitzah`, `rosh-hashanah`, `taanit`, `megillah`, `moed-katan`, `chagigah`, `yevamot`, `ketubot`, `nedarim`, `nazir`, `sotah`, `gittin`, `kiddushin`, `bava-kamma`, `bava-metzia`, `bava-batra`, `sanhedrin`, `makkot`, `shevuot`, `avodah-zarah`, `horayot`, `zevachim`, `menachot`, `chullin`, `bekhorot`, `arakhin`, `temurah`, `keritot`, `meilah`, `tamid`, `niddah`

### Book of Mormon

- **Source**: raw.githubusercontent.com/BraydenTW/book-of-mormon-api/refs/heads/main/book-of-mormon.json
- **Books**: 15
- **`chapter`**: Chapter number (1-indexed)
- **`verse`**: Verse number parsed from `reference` field or inferred by position
- **`lang`**: Always `en`
- **Book slugs**: `1nephi`, `2nephi`, `jacob`, `enos`, `jarom`, `omni`, `wordsofmormon`, `mosiah`, `alma`, `helaman`, `3nephi`, `4nephi`, `mormon`, `ether`, `moroni`

### Hindu

- **Sources**: Various public APIs
  - Bhagavad Gita: `raw.githubusercontent.com/bhavykhatri/DharmicData/main`
  - Ramayana: 'raw.githubusercontent.com/imradhe/ramayanam-api/main' Full CSV
- **Books**: 7 (`bhagavadgita`, `ramayana-1` through `ramayana-6`)
- **`chapter`**: Chapter / kanda number
- **`verse`**: Verse / shloka number
- **`lang`**: `sa` (Sanskrit) and `en` (English)

### Shakespeare

- **Source**: Folger Digital Library (`folgerdigitaltexts.org`)  HTML scraping
- **Books**: 37 plays
- **`chapter`**: Act number
- **`verse`**: Line index within the act/scene (sequential, not traditional line numbers)
- **`lang`**: Always `en`
- **Note**: Speaker names are prepended to line text in the format `SPEAKER: line text`
- **Book slugs**: `allswell`, `asyoulikeit`, `comedy_errors`, `cymbeline`, `lll`, `measure`, `merchant`, `merry_wives`, `midsummer`, `much_ado`, `pericles`, `taming_shrew`, `tempest`, `troilus_cressida`, `twelfth_night`, `two_gentlemen`, `winters_tale`, `cleopatra`, `coriolanus`, `hamlet`, `julius_caesar`, `lear`, `macbeth`, `othello`, `romeo_juliet`, `timon`, `titus`, `1henryiv`, `2henryiv`, `henryv`, `1henryvi`, `2henryvi`, `3henryvi`, `henryviii`, `john`, `richardii`, `richardiii`

---

## Inline Newline Encoding

Multi-line text values (primarily Shakespeare and Talmud) use `\x1F` (ASCII Unit Separator) as an inline line break within the `text` column. This allows multi-line passages to be stored as a single Parquet string without breaking the line-delimited TCP protocol. The CLI function decodes `\x1F` back to `\n`.

---

## Storage Layout

```
data/parquet/
  <library>/
    <book>/
      <uuid>.parquet
      ...
```

Each `<book>` directory is a Parquet dataset written by `pq.write_to_dataset()` with `compression="snappy"`. Spark reads the entire directory as a single logical table via `spark.read.parquet(<book_dir>)`.
