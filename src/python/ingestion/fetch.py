"""
Downloads raw JSON from external APIs and saves to data/raw/.
Parsing is done by ingest.py.

Usage:
    Called by libquery download
    python -m ingestion.fetch bible mark
    python -m ingestion.fetch bible          # entire bible
    python -m ingestion.fetch quran
"""

from __future__ import annotations

import json
import os
import sys
import time

import itertools
import threading

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import LIBRARY_CONFIG, RAW_DATA_DIR

def spinner(label, stop_event):
    for char in itertools.cycle("/-\\|"):
        if stop_event.is_set():
            break
        sys.stdout.write(f"\r{label} {char}")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * (len(label) + 2) + "\r")  # clear line



# Bible book name -> API number (getbible.net uses 1-66)
BIBLE_BOOK_NUMS: dict[str, int] = {
    "genesis": 1, "exodus": 2, "leviticus": 3, "numbers": 4,
    "deuteronomy": 5, "joshua": 6, "judges": 7, "ruth": 8,
    "1 samuel": 9, "2 samuel": 10, "1 kings": 11, "2 kings": 12,
    "1 chronicles": 13, "2 chronicles": 14, "ezra": 15, "nehemiah": 16,
    "esther": 17, "job": 18, "psalms": 19, "proverbs": 20,
    "ecclesiastes": 21, "song of solomon": 22, "isaiah": 23, "jeremiah": 24,
    "lamentations": 25, "ezekiel": 26, "daniel": 27, "hosea": 28,
    "joel": 29, "amos": 30, "obadiah": 31, "jonah": 32, "micah": 33,
    "nahum": 34, "habakkuk": 35, "zephaniah": 36, "haggai": 37,
    "zechariah": 38, "malachi": 39, "matthew": 40, "mark": 41,
    "luke": 42, "john": 43, "acts": 44, "romans": 45,
    "1 corinthians": 46, "2 corinthians": 47, "galatians": 48,
    "ephesians": 49, "philippians": 50, "colossians": 51,
    "1 thessalonians": 52, "2 thessalonians": 53, "1 timothy": 54,
    "2 timothy": 55, "titus": 56, "philemon": 57, "hebrews": 58,
    "james": 59, "1 peter": 60, "2 peter": 61, "1 john": 62,
    "2 john": 63, "3 john": 64, "jude": 65, "revelation": 66,
}


def _save(library: str, filename: str, data: dict) -> str:
    """Save a dict as JSON under data/raw/<library>/<filename>.json"""
    out_dir = os.path.join(RAW_DATA_DIR, library)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{filename}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {out_path}")
    return out_path


def fetch_bible(book: str | None = None) -> list[str]:

    #Fetch one Bible book or the full KJV.
    #Returns list of saved file paths.

    cfg = LIBRARY_CONFIG["bible"]
    base = cfg["base_url"]
    saved = []

    if book is None:
        # Full bible
        stop = threading.Event()
        t = threading.Thread(target=spinner, args="Fetching full Bible (KJV)…")
        t.start()
        r = requests.get(f"{base}.json", timeout=30)
        r.raise_for_status()
        stop.set()
        t.join()
        
        print(f"Done fetching the Bible (KJV)")
        saved.append(_save("bible", "full_kjv", r.json()))
    else:
        book_key = book.lower()
        num = BIBLE_BOOK_NUMS.get(book_key)
        if num is None:
            raise ValueError(f"Unknown Bible book: '{book}'")
        
        stop = threading.Event()
        t = threading.Thread(target=spinner, args= f"Fetching Bible / {book_key} (book #{num})…")
        t.start()
        r = requests.get(f"{base}/{num}.json", timeout=30)
        r.raise_for_status()
        stop.set()
        t.join()

        print(f"Done fetching the book of {book_key} (book #{num})")
        saved.append(_save("bible", book_key, r.json()))

    return saved


def fetch_quran() -> list[str]:
    # Fetch Arabic and English Quran and save both
    cfg = LIBRARY_CONFIG["quran"]
    saved = []

    stop = threading.Event()
    t = threading.Thread(target=spinner, args=("Fetching Quran (Arabic)…", stop))
    t.start()

    r = requests.get(cfg["arabic_url"], timeout=60)
    r.raise_for_status()
    stop.set()
    t.join()

    print("Done fetching Quran in Arabic")

    saved.append(_save("quran", "arabic", r.json()))

    time.sleep(1)  # rate limit

    stop = threading.Event()
    t = threading.Thread(target=spinner, args=("Fetching Quran (English)…", stop))
    t.start()

    r = requests.get(cfg["english_url"], timeout=60)
    r.raise_for_status()
    stop.set()
    t.join()

    print("Done fetching Quran in English")
    saved.append(_save("quran", "english_asad", r.json()))

    return saved


def fetch(library: str, book: str | None = None) -> list[str]:
    # Entry point used by c download cmd and by ingest
    library = library.lower()
    if library == "bible":
        return fetch_bible(book)
    if library == "quran":
        return fetch_quran()
    return [f"Unsupported library: '{library}'"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m ingestion.fetch <library> [book]")
        sys.exit(1)
    _lib  = sys.argv[1]
    _book = sys.argv[2] if len(sys.argv) > 2 else None
    fetch(_lib, _book)
