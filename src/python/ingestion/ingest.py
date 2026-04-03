from __future__ import annotations

import csv
import json
import os
import sys
from typing import Iterator

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import RAW_DATA_DIR, PARQUET_DIR

SCHEMA = pa.schema([
    pa.field("library", pa.string()),
    pa.field("book", pa.string()),
    pa.field("chapter", pa.int32()),
    pa.field("verse", pa.int32()),
    pa.field("text", pa.string()),
    pa.field("lang", pa.string()),  
])

Row = dict  # {"library","book","chapter","verse","text","lang"}

# Parser
def _rows_from_getbible(data: dict, library: str) -> Iterator[Row]:

    # keys: translation, name, chapters -> [chapter, verses ->[verse, text]]
    if "stdout" in data and "chapters" not in data:
        data = json.loads(data["stdout"])

    book_name = data.get("name", "unknown").lower()
    for ch in data.get("chapters", []):
        ch_num = int(ch["chapter"])
        for v in ch.get("verses", []):
            yield {
                "library": library,
                "book":    book_name,
                "chapter": ch_num,
                "verse":   int(v["verse"]),
                "text":    v["text"].strip(),
                "lang":    "en",
            }


def _rows_from_quran(arabic_data: dict, english_data: dict) -> Iterator[Row]:
    """
    Parse api.alquran.cloud format.
    Merges Arabic and English side by side
    one row per verse, two lang values.
    
    For surahs : number, verse -> [numberInSurah, text, surah.englishName]
    """
    ar_surahs = arabic_data["data"]["surahs"]
    en_surahs = english_data["data"]["surahs"]

    for ar_s, en_s in zip(ar_surahs, en_surahs):
        surah_num  = int(ar_s["number"])
        surah_name = ar_s.get("englishName", f"surah_{surah_num}").lower().replace(" ", "_")

        for ar_v, en_v in zip(ar_s["ayahs"], en_s["ayahs"]):
            verse_num = int(ar_v["numberInSurah"])
            # Arabic row
            yield {
                "library": "quran",
                "book": surah_name,
                "chapter":surah_num,
                "verse": verse_num,
                "text": ar_v["text"].strip(),
                "lang": "ar",
            }
            # English row
            yield {
                "library": "quran",
                "book": surah_name,
                "chapter":surah_num,
                "verse": verse_num,
                "text":en_v["text"].strip(),
                "lang":"en",
            }

# Writer
def _write_parquet(rows: list[Row], library: str, book: str) -> str:
    """Convert rows to an Arrow table and write partitioned Parquet."""
    if not rows:
        raise ValueError("No rows to write")

    table = pa.table({
        "library": pa.array([r["library"] for r in rows], type=pa.string()),
        "book":    pa.array([r["book"]    for r in rows], type=pa.string()),
        "chapter": pa.array([r["chapter"] for r in rows], type=pa.int32()),
        "verse":   pa.array([r["verse"]   for r in rows], type=pa.int32()),
        "text":    pa.array([r["text"]    for r in rows], type=pa.string()),
        "lang":    pa.array([r["lang"]    for r in rows], type=pa.string()),
    }, schema=SCHEMA)

    out_dir = os.path.join(PARQUET_DIR, library, book)
    os.makedirs(out_dir, exist_ok=True)
    pq.write_to_dataset(
        table,
        root_path=out_dir,
        compression="snappy",
        existing_data_behavior="overwrite_or_ignore",
    )
    print(f"  Wrote {len(rows)} rows -> {out_dir}")
    return out_dir


def ingest_bible_json(json_path: str, library: str = "bible") -> str:
    """Ingest a single Bible book JSON file (getbible format)."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    rows = list(_rows_from_getbible(data, library))
    book = rows[0]["book"] if rows else os.path.splitext(os.path.basename(json_path))[0]
    print(f"Ingesting {library}/{book} from JSON ({len(rows)} verses)…")
    return _write_parquet(rows, library, book)


def ingest_quran_json(arabic_path: str, english_path: str) -> str:
    # Ingest Arabic and English Quran json
    with open(arabic_path,  encoding="utf-8") as f: ar = json.load(f)
    with open(english_path, encoding="utf-8") as f: en = json.load(f)

    rows = list(_rows_from_quran(ar, en))
    print(f"Ingesting quran ({len(rows)} rows, Arabic + English)…")

    return _write_parquet(rows, "quran", "all")



def ingest(library: str, book: str | None = None) -> str: #book is nullable
    """
    Main entry point
    """
    library = library.lower()

    if library == "quran":
        ar_path = os.path.join(RAW_DATA_DIR, "quran", "arabic.json")
        en_path = os.path.join(RAW_DATA_DIR, "quran", "english.json")
        for p in (ar_path, en_path):
            if not os.path.exists(p):
                raise FileNotFoundError(f"Raw file missing: {p}  : run fetch first")
        return ingest_quran_json(ar_path, en_path)

    if library == "bible":
        json_path = os.path.join(RAW_DATA_DIR, "bible", f"{book.lower()}.json")
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Raw file missing: {json_path}  : run fetch first")
        return ingest_bible_json(json_path, library)

    raise ValueError(f"Unsupported library: '{library}'")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("library")
    ap.add_argument("book", nargs="?")
    args = ap.parse_args()
    ingest(args.library, args.book)
