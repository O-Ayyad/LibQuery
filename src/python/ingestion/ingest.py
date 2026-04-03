from __future__ import annotations

import json
import os
import sys
from abc import ABC, abstractmethod
from typing import Iterator

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import RAW_DATA_DIR, PARQUET_DIR

# ---------------------------------------------------------------------------
# Schema / Row
# ---------------------------------------------------------------------------

SCHEMA = pa.schema([
    pa.field("library", pa.string()),
    pa.field("book",    pa.string()),
    pa.field("chapter", pa.int32()),
    pa.field("verse",   pa.int32()),
    pa.field("text",    pa.string()),
    pa.field("lang",    pa.string()),
])

Row = dict  # keys: library, book, chapter, verse, text, lang

# Library base class

class Library(ABC):
    #Subclass this for every new text corpus.

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def raw_files(self) -> list[str]: ...

    @abstractmethod
    def parse(self, book_filter: str | None = None) -> Iterator[Row]: ...

    def validate_files(self) -> None:
        for path in self.raw_files:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Missing: {path} – run fetch first.")


class Bible(Library):

    @property
    def name(self) -> str:
        return "bible"

    @property
    def raw_files(self) -> list[str]:
        return [os.path.join(RAW_DATA_DIR, "bible", "bible.json")]

    def parse(self, book_filter: str | None = None) -> Iterator[Row]:
        with open(self.raw_files[0], encoding="utf-8") as f:
            data = json.load(f)

        for book_obj in data.get("books", []):
            book_name = book_obj["name"].lower()
            if book_filter and book_name != book_filter:
                continue
            for ch in book_obj.get("chapters", []):
                ch_num = int(ch["chapter"])
                for v in ch.get("verses", []):
                    text = v["text"].strip()
                    if not text:
                        continue
                    yield {
                        "library": self.name,
                        "book":    book_name,
                        "chapter": ch_num,
                        "verse":   int(v["verse"]),
                        "text":    text,
                        "lang":    "en",
                    }


class Quran(Library):

    @property
    def name(self) -> str:
        return "quran"

    @property
    def raw_files(self) -> list[str]:
        return [
            os.path.join(RAW_DATA_DIR, "quran", "arabic.json"),
            os.path.join(RAW_DATA_DIR, "quran", "english.json"),
        ]

    def parse(self, book_filter: str | None = None) -> Iterator[Row]:
        with open(self.raw_files[0], encoding="utf-8") as f: ar = json.load(f)
        with open(self.raw_files[1], encoding="utf-8") as f: en = json.load(f)

        ar_surahs = ar["data"]["surahs"]
        en_surahs = en["data"]["surahs"]

        if len(ar_surahs) != len(en_surahs):
            raise ValueError(
                f"Surah count mismatch: Arabic={len(ar_surahs)}, "
                f"English={len(en_surahs)}"
            )

        for ar_s, en_s in zip(ar_surahs, en_surahs):
            if len(ar_s["ayahs"]) != len(en_s["ayahs"]):
                raise ValueError(
                    f"Ayah count mismatch in surah {ar_s['number']}: "
                    f"Arabic={len(ar_s['ayahs'])}, English={len(en_s['ayahs'])}"
                )

            surah_num  = int(ar_s["number"])
            surah_name = ar_s.get("englishName", f"surah_{surah_num}") \
                            .lower().replace(" ", "_")

            if book_filter and surah_name != book_filter:
                continue

            for ar_v, en_v in zip(ar_s["ayahs"], en_s["ayahs"]):
                verse_num = int(ar_v["numberInSurah"])
                yield {
                    "library": self.name, "book": surah_name,
                    "chapter": surah_num, "verse": verse_num,
                    "text": ar_v["text"].strip(), "lang": "ar",
                }
                yield {
                    "library": self.name, "book": surah_name,
                    "chapter": surah_num, "verse": verse_num,
                    "text": en_v["text"].strip(), "lang": "en",
                }



# Registry 
# Create library class and register here

LIBRARIES: dict[str, Library] = {
    lib.name: lib for lib in [
        Bible(),
        Quran(),
    ]
}

# Writer

def _write_parquet(rows: list[Row], library: str, book: str) -> str:
    if not rows:
        raise ValueError(f"No rows to write for {library}/{book}")

    table = pa.table(
        {
            "library": pa.array([r["library"] for r in rows], pa.string()),
            "book":    pa.array([r["book"]    for r in rows], pa.string()),
            "chapter": pa.array([r["chapter"] for r in rows], pa.int32()),
            "verse":   pa.array([r["verse"]   for r in rows], pa.int32()),
            "text":    pa.array([r["text"]    for r in rows], pa.string()),
            "lang":    pa.array([r["lang"]    for r in rows], pa.string()),
        },
        schema=SCHEMA,
    )

    out_dir = os.path.join(PARQUET_DIR, library, book)
    os.makedirs(out_dir, exist_ok=True)
    pq.write_to_dataset(
        table,
        root_path=out_dir,
        compression="snappy",
        existing_data_behavior="overwrite_or_ignore",
    )
    print(f" Success! {library}/{book}  {len(rows)} rows  ->  {out_dir}")
    return out_dir


def ingest(target: str = "all") -> list[str]:
    """
    Args:
        target: "all"  every registered library
                "<library>"  full library, e.g. "bible", "quran"
                "<library>:<book>" single book,  e.g. "bible:genesis"
        List of Parquet output dirs
    """
    target= target.lower().strip()
    parts = target.split(":", 1)
    library_key = parts[0]
    book_filter = parts[1] if len(parts) == 2 else None

    # resolve which libraries to run
    if library_key == "all":
        if book_filter:
            raise ValueError("Cannot use book filter with 'all'.")
        targets: list[Library] = list(LIBRARIES.values())
    elif library_key in LIBRARIES:
        targets = [LIBRARIES[library_key]]
    else:
        raise ValueError(
            f"Unknown library '{library_key}'. "
            f"Registered: {', '.join(LIBRARIES)}"
        )

    out_dirs: list[str] = []

    for lib in targets:
        lib.validate_files()

        current_book: str | None = None
        book_rows: list[Row] = []

        for row in lib.parse(book_filter):
            if row["book"] != current_book:
                if book_rows:
                    out_dirs.append(_write_parquet(book_rows, lib.name, current_book))
                current_book = row["book"]
                book_rows    = []
            book_rows.append(row)

        if book_rows:
            out_dirs.append(_write_parquet(book_rows, lib.name, current_book))

        if book_filter and not out_dirs:
            raise ValueError(
                f"Book '{book_filter}' not found in {lib.name}. "
                "Check spelling."
            )
    return out_dirs

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "target", nargs="?", default="all",
        help=f"all | {'| '.join(LIBRARIES)} | <library>:<book>  (default: all)"
    )
    args = ap.parse_args()
    ingest(args.target)