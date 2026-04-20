from __future__ import annotations

import json
import os
import sys
from abc import ABC, abstractmethod
from typing import Iterator
import unicodedata
import re
from networking.registry import LIBRARY_BOOKS
import pyarrow as pa
import pyarrow.parquet as pq
from typing import Callable


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import RAW_DATA_DIR
from config.storage import get_fs, book_path, rmdir, mkdirs

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


_HTML_TAG = re.compile(r"<[^>]+>")

def _strip_html(text: str) -> str:
    return _HTML_TAG.sub("", text).strip()

Row = dict  # keys: library, book, chapter, verse, text, lang

# Library base class

class Library(ABC):
    #Subclass this for every new text library.
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def raw_files(self) -> list[str]: ...

    @abstractmethod
    def parse(self, book_filter: str | None = None) -> Iterator[Row]: ...

    def validate_files(self) -> None:
        for path in self.raw_files:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Missing: {path} - run fetch first.")
    @classmethod
    def for_book(cls, book: str) -> "Library":
        return cls(book=book)

class Bible(Library):

    def __init__(self, book: str | None = None):
        self._book = book

    @property
    def name(self) -> str:
        return "bible"

    @property
    def raw_files(self) -> list[str]:
        if self._book:
            return [os.path.join(RAW_DATA_DIR, "bible", f"{self._book}.json")]
        return [os.path.join(RAW_DATA_DIR, "bible", "bible.json")]

    def parse(self, book_filter: str | None = None) -> Iterator[Row]:
        with open(self.raw_files[0], encoding="utf-8") as f:
            data = json.load(f)

        if "books" in data:
            books = data["books"]
        else:
            books = [data]  

        for book_obj in books:
            book_name = book_obj["name"].lower().replace(" ", "")
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

    def __init__(self, book: str | None = None):
        self._book = book

    @property
    def name(self) -> str:
        return "quran"

    @property
    def raw_files(self) -> list[str]:
        return [
            os.path.join(RAW_DATA_DIR, "quran", "arabic.json"),
            os.path.join(RAW_DATA_DIR, "quran", "english_asad.json"),
        ]

    def parse(self, book_filter: str | None = None) -> Iterator[Row]:
            with open(self.raw_files[0], encoding="utf-8") as f:
                ar = json.load(f)
            with open(self.raw_files[1], encoding="utf-8") as f:
                en = json.load(f)

            ar_surahs = ar["data"]["surahs"]
            en_surahs = en["data"]["surahs"]

            if len(ar_surahs) != len(en_surahs):
                raise ValueError(
                    f"Surah count mismatch: Arabic={len(ar_surahs)}, English={len(en_surahs)}"
                )

            for ar_s, en_s in zip(ar_surahs, en_surahs):
                if len(ar_s["ayahs"]) != len(en_s["ayahs"]):
                    raise ValueError(
                        f"Ayah count mismatch in surah {ar_s['number']}: "
                        f"Arabic={len(ar_s['ayahs'])}, English={len(en_s['ayahs'])}"
                    )

                surah_num = int(ar_s["number"])
                raw_name = ar_s.get("englishName", f"surah_{surah_num}")

                normalized = unicodedata.normalize("NFKD", raw_name)
                sanitized = normalized.lower().replace(" ", "_")
                surah_name = re.sub(r"[^\w\-]", "", sanitized)

                if book_filter and surah_name != book_filter:
                    continue

                for ar_v, en_v in zip(ar_s["ayahs"], en_s["ayahs"]):
                    verse_num = int(ar_v["numberInSurah"])
                    yield {
                        "library": self.name,
                        "book": surah_name,
                        "chapter": surah_num,
                        "verse": verse_num,
                        "text": ar_v["text"].strip(),
                        "lang": "ar",
                    }
                    yield {
                        "library": self.name,
                        "book": surah_name,
                        "chapter": surah_num,
                        "verse": verse_num,
                        "text": en_v["text"].strip(),
                        "lang": "en",
                    }
class Talmud(Library):

    def __init__(self, book: str | None = None):
        self._book = book

    @property
    def name(self) -> str:
        return "talmud"

    @property
    def raw_files(self) -> list[str]:
        if self._book:
            return [os.path.join(RAW_DATA_DIR, "talmud", f"{self._book}.json")]
        return [
            os.path.join(RAW_DATA_DIR, "talmud", f"{b}.json")
            for b in LIBRARY_BOOKS["talmud"]
        ]

    def parse(self, book_filter: str | None = None) -> Iterator[Row]:
            files = (
                [os.path.join(RAW_DATA_DIR, "talmud", f"{book_filter}.json")]
                if book_filter else self.raw_files
            )
            for path in files:
                if not os.path.exists(path):
                    continue
                tractate_name = os.path.splitext(os.path.basename(path))[0]
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    print(f"WARNING: could not read {path}: {e}", flush=True)
                    continue
                for lang, text_data in (("en", data.get("text", [])),
                                        ("he", data.get("he", []))):
                    if not text_data:
                        continue
                    daf_idx = 0
                    for daf in text_data:
                        if daf is None:
                            continue
                        if isinstance(daf, str):
                            daf = [daf]
                        if not isinstance(daf, list) or not daf:
                            continue
                        daf_idx += 1
                        for amud_idx, segment in enumerate(daf, start=1):
                            if not segment or not isinstance(segment, str) or not segment.strip():
                                continue
                            clean = _strip_html(segment)
                            if not clean:
                                continue
                            yield {
                                "library": self.name,
                                "book":    tractate_name,
                                "chapter": daf_idx,
                                "verse":   amud_idx,
                                "text":    clean,
                                "lang":    lang,
                            }

class Hindu(Library):

    def __init__(self, book: str | None = None):
        self._book = book

    @property
    def name(self) -> str:
        return "hindu"

    @property
    def raw_files(self) -> list[str]:
        if self._book:
            return [os.path.join(RAW_DATA_DIR, "hindu", f"{self._book}.json")]
        return [
            os.path.join(RAW_DATA_DIR, "hindu", f"{b}.json")
            for b in LIBRARY_BOOKS["hindu"]
        ]

    def parse(self, book_filter: str | None = None) -> Iterator[Row]:
        files = (
            [os.path.join(RAW_DATA_DIR, "hindu", f"{book_filter}.json")]
            if book_filter else self.raw_files
        )
        for path in files:
            if not os.path.exists(path):
                continue
            book_name = os.path.splitext(os.path.basename(path))[0]
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            if book_name == "bhagavadgita":
                yield from self._parse_gita(data, book_name)
                
            #elif book_name.startswith("rigveda-"):
            #    yield from self._parse_rigveda(data, book_name)

            elif book_name.startswith("ramayana-"):
                yield from self._parse_ramayana(data, book_name)

            #else:
            #    yield from self._parse_upanishad(data, book_name)


    def _parse_gita(self, data: dict, book_name: str) -> Iterator[Row]:
        for v in data.get("chapters", []):
            ch_num = int(v["chapter"])
            verse_num = int(v["verse"])

            sa_text = re.sub(r"।।\d+\.\d+।।", "", v.get("text", "")).strip()
            if sa_text:
                yield {
                    "library": self.name, "book": book_name,
                    "chapter": ch_num, "verse": verse_num,
                    "text": sa_text, "lang": "sa",
                }

            en_text = v.get("translations", {}).get("swami sivananda", "").strip()
            en_text = re.sub(r"^\d+\.\d+\.?\s*", "", en_text).strip()
            if en_text:
                yield {
                    "library": self.name, "book": book_name,
                    "chapter": ch_num, "verse": verse_num,
                    "text": en_text, "lang": "en",
                }
    #API returns csv file
    def _parse_ramayana(self, data: dict, book_name: str) -> Iterator[Row]:
        for sloka in data.get("slokas", []):
            sarga = int(sloka.get("sarga", 0))
            sloka_num = int(sloka.get("sloka", 0))

            sa_text = sloka.get("text", "").strip()
            sa_text = re.sub(r"।।[\d.]+।।", "", sa_text).strip()

            en_text = sloka.get("translation", "")
            if isinstance(en_text, str):
                en_text = re.sub(r"<[^>]+>", "", en_text).strip()

            if sa_text:
                yield {
                    "library": self.name, "book": book_name,
                    "chapter": sarga, "verse": sloka_num,
                    "text": sa_text, "lang": "sa",
                }
            if en_text:
                yield {
                    "library": self.name, "book": book_name,
                    "chapter": sarga, "verse": sloka_num,
                    "text": en_text, "lang": "en",
                }
class Mormon(Library):

    def __init__(self, book: str | None = None):
        self._book = book

    @property
    def name(self) -> str:
        return "mormon"

    @property
    def raw_files(self) -> list[str]:
        if self._book:
            return [os.path.join(RAW_DATA_DIR, "mormon", f"{self._book}.json")]
        return [
            os.path.join(RAW_DATA_DIR, "mormon", f"{b}.json")
            for b in LIBRARY_BOOKS["mormon"]
        ]

    def parse(self, book_filter: str | None = None) -> Iterator[Row]:
        files = (
            [os.path.join(RAW_DATA_DIR, "mormon", f"{book_filter}.json")]
            if book_filter else self.raw_files
        )
        for path in files:
            if not os.path.exists(path):
                continue
            book_name = os.path.splitext(os.path.basename(path))[0]
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            for ch_obj in data.get("chapters", []):
                ch_num = int(ch_obj.get("chapter", 0))
                for v in ch_obj.get("verses", []):
                    text = v.get("text", "").strip()
                    if not text:
                        continue
                    yield {
                        "library": self.name,
                        "book":    book_name,
                        "chapter": ch_num,
                        "verse":   int(v.get("verse", 0)),
                        "text":    text,
                        "lang":    "en",
                    }


# Registry 
# Create library class and register here

LIBRARIES: dict[str, type[Library]] = {
    "bible":  Bible,
    "quran":  Quran,
    "talmud": Talmud,
    "hindu":  Hindu,
    "mormon": Mormon,
}

# Writer

def _write_parquet(rows: list[Row], library: str, book: str, send:Callable[[str], None]=print) -> str:
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

    out_dir = book_path(library, book)
    rmdir(out_dir)
    mkdirs(out_dir)

    pq.write_to_dataset(
        table,
        root_path=out_dir,
        filesystem=get_fs(),
        compression="snappy",
        existing_data_behavior="overwrite_or_ignore",
    )
    send(f" Success! {library}/{book}  {len(rows)} rows")
    return out_dir


def ingest(target: str = "all", send:Callable[[str],None]=print) -> list[str]:
    target = target.lower().strip()
    parts = target.split(":", 1)
    library_key = parts[0]
    book_filter = parts[1] if len(parts) == 2 else None

    if library_key == "all":
        if book_filter:
            raise ValueError("Cannot use book filter with 'all'.")
        targets: list[Library] = [cls() for cls in LIBRARIES.values()]
    elif library_key in LIBRARIES:
        cls = LIBRARIES[library_key]
        targets = [cls.for_book(book_filter) if book_filter else cls()]
        book_filter = None
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

        try:
            for row in lib.parse(book_filter):
                if row["book"] != current_book:
                    if book_rows:
                        out_dirs.append(_write_parquet(book_rows, lib.name, current_book, send))
                    current_book = row["book"]
                    book_rows = []
                book_rows.append(row)
        except Exception as e:
            send(f"[ingest] ERROR: parse failed for {lib.name}/{current_book or '?'}: {e}")

        if book_rows:
            out_dirs.append(_write_parquet(book_rows, lib.name, current_book, send))

        if book_filter and not out_dirs:
            send(f"Book '{book_filter}' not found in {lib.name}. Check spelling.")
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