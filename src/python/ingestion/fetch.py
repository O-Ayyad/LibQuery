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

from ingestion.ingest import ingest
import threading

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import LIBRARY_CONFIG, RAW_DATA_DIR
from typing import Callable



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

#for sql query
QURAN_SURAHS = {
    1: "al-faatiha", 2: "al-baqara", 3: "aal-i-imraan", 4: "an-nisaa",
    5: "al-maaida", 6: "al-anaam", 7: "al-araaf", 8: "al-anfaal",
    9: "at-tawba", 10: "yunus", 11: "hud", 12: "yusuf",
    13: "ar-rad", 14: "ibrahim", 15: "al-hijr", 16: "an-nahl",
    17: "al-israa", 18: "al-kahf", 19: "maryam", 20: "taa-haa",
    21: "al-anbiyaa", 22: "al-hajj", 23: "al-muminoon", 24: "an-noor",
    25: "al-furqaan", 26: "ash-shuaraa", 27: "an-naml", 28: "al-qasas",
    29: "al-ankaboot", 30: "ar-room", 31: "luqman", 32: "as-sajda",
    33: "al-ahzaab", 34: "saba", 35: "faatir", 36: "yaseen",
    37: "as-saaffaat", 38: "saad", 39: "az-zumar", 40: "ghafir",
    41: "fussilat", 42: "ash-shura", 43: "az-zukhruf", 44: "ad-dukhaan",
    45: "al-jaathiya", 46: "al-ahqaf", 47: "muhammad", 48: "al-fath",
    49: "al-hujuraat", 50: "qaaf", 51: "adh-dhaariyat", 52: "at-tur",
    53: "an-najm", 54: "al-qamar", 55: "ar-rahmaan", 56: "al-waaqia",
    57: "al-hadid", 58: "al-mujaadila", 59: "al-hashr", 60: "al-mumtahana",
    61: "as-saff", 62: "al-jumua", 63: "al-munaafiqoon", 64: "at-taghaabun",
    65: "at-talaaq", 66: "at-tahrim", 67: "al-mulk", 68: "al-qalam",
    69: "al-haaqqa", 70: "al-maaarij", 71: "nooh", 72: "al-jinn",
    73: "al-muzzammil", 74: "al-muddaththir", 75: "al-qiyaama", 76: "al-insaan",
    77: "al-mursalaat", 78: "an-naba", 79: "an-naaziaat", 80: "abasa",
    81: "at-takwir", 82: "al-infitaar", 83: "al-mutaffifin", 84: "al-inshiqaaq",
    85: "al-burooj", 86: "at-taariq", 87: "al-alaa", 88: "al-ghaashiya",
    89: "al-fajr", 90: "al-balad", 91: "ash-shams", 92: "al-lail",
    93: "ad-dhuhaa", 94: "ash-sharh", 95: "at-tin", 96: "al-alaq",
    97: "al-qadr", 98: "al-bayyina", 99: "az-zalzala", 100: "al-aadiyaat",
    101: "al-qaaria", 102: "at-takaathur", 103: "al-asr", 104: "al-humaza",
    105: "al-fil", 106: "quraish", 107: "al-maaun", 108: "al-kawthar",
    109: "al-kaafiroon", 110: "an-nasr", 111: "al-masad", 112: "al-ikhlaas",
    113: "al-falaq", 114: "an-naas"
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


def fetch_bible(book: str | None = None, send = Callable[[str], None]) -> list[str]:

    #Fetch one Bible book or the full KJV.
    #Returns list of saved file paths.

    cfg = LIBRARY_CONFIG["bible"]
    base = cfg["base_url"]
    saved = []

    if book is None:
        # Full bible
        send("Fetching full Bible (KJV)...\n")
        r = requests.get(f"{base}.json", timeout=30)
        r.raise_for_status()
        
        send(f"Done fetching the Bible (KJV)")
        saved.append(_save("bible", "bible", r.json()))
        ingest("bible",send)
    else:
        book_key = book.lower()
        num = BIBLE_BOOK_NUMS.get(book_key)
        if num is None:
            msg = f"Unknown Bible book: '{book}'"
            send(msg)
            raise ValueError(msg)
        
        send(f"Fetching Bible / {book_key} (book #{num})...\n")
        r = requests.get(f"{base}/{num}.json", timeout=30)
        r.raise_for_status()

        send(f"Done fetching the book of {book_key} (book #{num})")
        saved.append(_save("bible", book_key, r.json()))
        ingest(f"bible:{book_key}",send)

    return saved


def fetch_quran(send = Callable[[str], None]) -> list[str]:
    # Fetch Arabic and English Quran and save both
    cfg = LIBRARY_CONFIG["quran"]
    saved = []

    send("Fetching Quran (Arabic)...\n")

    r = requests.get(cfg["arabic_url"], timeout=60)
    r.raise_for_status()

    send("Done fetching Quran in Arabic")

    saved.append(_save("quran", "arabic", r.json()))

    time.sleep(1)  # rate limit

    send("Fetching Quran (English)...\n")
    r = requests.get(cfg["english_url"], timeout=60)
    r.raise_for_status()


    send("Done fetching Quran in English")
    saved.append(_save("quran", "english_asad", r.json()))
    ingest("quran",send) 
    return saved


def fetch(library: str, book: str | None = None, send = Callable[[str], None]) -> list[str]:
    # Entry point used by c download cmd and by ingest
    library = library.lower()
    if library == "bible":
        return fetch_bible(book,send)
    if library == "quran":
        return fetch_quran(send)
    return [f"Unsupported library: '{library}'"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: libquery download <library> [book]")
        sys.exit(1)
    _lib  = sys.argv[1]
    _book = sys.argv[2] if len(sys.argv) > 2 else None
    fetch(_lib, _book)
