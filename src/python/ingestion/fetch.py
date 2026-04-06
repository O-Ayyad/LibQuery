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
from networking.registry import is_downloaded, missing_books, is_known, LIBRARY_BOOKS

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import LIBRARY_CONFIG, RAW_DATA_DIR
from typing import Callable
import shutil


# Bible book name -> API number (getbible.net uses 1-66)
BIBLE_BOOK_NUMS: dict[str, int] = {
    "genesis": 1, "exodus": 2, "leviticus": 3, "numbers": 4,
    "deuteronomy": 5, "joshua": 6, "judges": 7, "ruth": 8,
    "1samuel": 9, "2samuel": 10, "1kings": 11, "2kings": 12,
    "1chronicles": 13, "2chronicles": 14, "ezra": 15, "nehemiah": 16,
    "esther": 17, "job": 18, "psalms": 19, "proverbs": 20,
    "ecclesiastes": 21, "songofsongs": 22, "isaiah": 23, "jeremiah": 24,
    "lamentations": 25, "ezekiel": 26, "daniel": 27, "hosea": 28,
    "joel": 29, "amos": 30, "obadiah": 31, "jonah": 32, "micah": 33,
    "nahum": 34, "habakkuk": 35, "zephaniah": 36, "haggai": 37,
    "zechariah": 38, "malachi": 39, "matthew": 40, "mark": 41,
    "luke": 42, "john": 43, "acts": 44, "romans": 45,
    "1corinthians": 46, "2corinthians": 47, "galatians": 48,
    "ephesians": 49, "philippians": 50, "colossians": 51,
    "1thessalonians": 52, "2thessalonians": 53, "1timothy": 54,
    "2timothy": 55, "titus": 56, "philemon": 57, "hebrews": 58,
    "james": 59, "1peter": 60, "2peter": 61, "1john": 62,
    "2john": 63, "3john": 64, "jude": 65, "revelation": 66,
}
BOOK_NAME_REMAP: dict[str, str] = {
    "songofsolomon": "songofsongs",
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

TALMUD_SEFARIA_REFS: dict[str, str] = {
    "berakhot":"Berakhot",
    "shabbat":"Shabbat",
    "eruvin":"Eruvin",
    "pesachim":"Pesachim",
    "yoma": "Yoma",
    "sukkah":"Sukkah",
    "beitzah":"Beitzah",
    "rosh-hashanah":"Rosh_Hashanah",
    "taanit":"Taanit",
    "megillah" : "Megillah",
    "moed-katan" :"Moed_Katan",
    "chagigah" :"Chagigah",
    "yevamot" : "Yevamot",
    "ketubot" : "Ketubot",
    "nedarim" :"Nedarim",
    "nazir": "Nazir",
    "sotah":"Sotah",
    "gittin":"Gittin",
    "kiddushin" :"Kiddushin",
    "bava-kamma": "Bava_Kamma",
    "bava-metzia":"Bava_Metzia",
    "bava-batra": "Bava_Batra",
    "sanhedrin": "Sanhedrin",
    "makkot":"Makkot",
    "shevuot":"Shevuot",
    "avodah-zarah": "Avodah_Zarah",
    "horayot":"Horayot",
    "zevachim":"Zevachim",
    "menachot" : "Menachot",
    "chullin" : "Chullin",
    "bekhorot" :"Bekhorot",
    "arakhin":"Arakhin",
    "temurah" :"Temurah",
    "keritot" :"Keritot",
    "meilah":"Meilah",
    "tamid":"Tamid",
    "niddah": "Niddah",
}
MORMON_TITLE_MAP: dict[str, str] = {
    "1nephi": "1 Nephi",
    "2nephi": "2 Nephi",
    "jacob":  "Jacob",
    "enos":"Enos",
    "jarom":"Jarom",
    "omni": "Omni",
    "wordsofmormon":"Words of Mormon",
    "mosiah": "Mosiah",
    "alma": "Alma",
    "helaman":"Helaman",
    "3nephi":"3 Nephi",
    "4nephi":"4 Nephi",
    "mormon": "Mormon",
    "ether": "Ether",
    "moroni":"Moroni",
}

RAMAYANA_FILES: dict[str, str] = {
    "bala":       "1_balakanda",
    "ayodhya":    "2_ayodhyakanda",
    "aranya":     "3_aranyakanda",
    "kishkindha": "4_kishkindhakanda",
    "sundara":    "5_sundarakanda",
    "yuddha":     "6_yudhhakanda",
    "uttara":     "7_uttarakanda",
}

def _save(library: str, filename: str, data: dict) -> str: #Save the data to the raw data directory
    """Save a dict as JSON under data/raw/<library>/<filename>.json"""
    out_dir = os.path.join(RAW_DATA_DIR, library)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{filename}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {out_path}")
    return out_path

def _cleanup_raw(library: str) -> None: #Clean up the raw data directory
    raw_dir = os.path.join(RAW_DATA_DIR, library)
    if os.path.isdir(raw_dir):
        shutil.rmtree(raw_dir)
        print(f"  Cleaned up {raw_dir}", flush=True)

def fetch_hindu(book: str | None = None, send: Callable[[str], None] = print) -> list[str]:
    saved: list[str] = []

    books_to_fetch = (
        [book.lower()] if book
        else [b for b in LIBRARY_BOOKS["hindu"] if not is_downloaded("hindu", b)]
    )

    if not books_to_fetch:
        send("Hindu texts are already fully downloaded.")
        return []

    for b in books_to_fetch:
        try:
            if b == "bhagavad-gita":
                saved += _fetch_gita(send)
            elif b.startswith("rigveda-"):
                mandala = int(b.split("-")[1])
                saved += _fetch_rigveda_mandala(mandala, send)
            elif b.startswith("ramayana-"):
                kanda = b.split("ramayana-")[1]
                saved += _fetch_ramayana_kanda(kanda, send)
            elif b in ("isha","kena","katha","prashna","mundaka",
                       "mandukya","taittiriya","aitareya","chandogya","brihadaranyaka"):
                saved += _fetch_upanishad(b, send)
            else:
                send(f"  Unknown hindu text: '{b}'")
        except Exception as e:
            send(f"  Error fetching {b}: {e}")
    _cleanup_raw("hindu")
    return saved


def _fetch_gita(send: Callable[[str], None]) -> list[str]:
    base = LIBRARY_CONFIG["hindu"]["gita_base"]
    send("Fetching Bhagavad Gita...")
    chapters = []
    for ch in range(1, 19):
        r = requests.get(f"{base}/chapter/{ch}", timeout=30)
        r.raise_for_status()
        verse_count = r.json()["data"][0]["verses_count"]

        verses = []
        for v in range(1, verse_count + 1):
            r2 = requests.get(f"{base}/text/translations/{ch}/{v}", timeout=30)
            r2.raise_for_status()
            translations = r2.json().get("data", [])
            en_text = next(
                (t["translation"] for t in translations if t["lang"] == "en"),
                None
            )
            r3 = requests.get(f"{base}/text/{ch}/{v}", timeout=30)
            r3.raise_for_status()
            shloka = r3.json()["data"][0]["shloka"] if r3.json().get("data") else ""
            verses.append({"verse": v, "shloka": shloka, "translation": en_text})
            time.sleep(0.1)

        chapters.append({"chapter": ch, "verses": verses})
        send(f"  Chapter {ch} done ({verse_count} verses)")

    path = _save("hindu", "bhagavad-gita", {"chapters": chapters})
    ingest("hindu:bhagavad-gita", send)
    return [path]


def _fetch_rigveda_mandala(mandala: int, send: Callable[[str], None]) -> list[str]:
    base = LIBRARY_CONFIG["hindu"]["dharmic_data_base"]
    send(f"Fetching Rigveda mandala {mandala}...")
    url = f"{base}/Rigveda/rigveda_mandala_{mandala}.json"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    path = _save("hindu", f"rigveda-{mandala}", r.json())
    ingest(f"hindu:rigveda-{mandala}", send)
    return [path]


def _fetch_ramayana_kanda(kanda: str, send: Callable[[str], None]) -> list[str]:
    base = LIBRARY_CONFIG["hindu"]["dharmic_data_base"]
    filename = RAMAYANA_FILES.get(kanda)
    if not filename:
        raise ValueError(f"Unknown kanda: '{kanda}'")
    send(f"Fetching Ramayana / {kanda} kanda...")
    url = f"{base}/ValmikiRamayana/{filename}.json"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    path = _save("hindu", f"ramayana-{kanda}", r.json())
    ingest(f"hindu:ramayana-{kanda}", send)
    return [path]


def _fetch_upanishad(name: str, send: Callable[[str], None]) -> list[str]:
    base = LIBRARY_CONFIG["hindu"]["upanishads_base"]
    send(f"Fetching Upanishad: {name}...")
    url = f"{base}/{name}.json"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    path = _save("hindu", name, r.json())
    ingest(f"hindu:{name}", send)
    return [path]

def fetch_talmud(book: str | None = None, send: Callable[[str], None] = print) -> list[str]:
    saved: list[str] = []
    base_url = LIBRARY_CONFIG["talmud"]["base_url"]

    books_to_fetch = ( #Get the books to fetch
        [book.lower()] if book
        else [b for b in LIBRARY_BOOKS["talmud"] if not is_downloaded("talmud", b)]
    )

    if not books_to_fetch:
        send("Talmud is already fully downloaded.")
        return []

    for tractate in books_to_fetch: #Fetch each tractate
        sefaria_ref = TALMUD_SEFARIA_REFS.get(tractate)
        if not sefaria_ref:
            send(f"  Unknown tractate: '{tractate}'")
            continue
        send(f"Fetching talmud/{tractate}...")
        try:
            r = requests.get(
                f"{base_url}/{sefaria_ref}",
                params={"lang": "bi", "pad": 0, "context": 0},
                timeout=60,
            )
            r.raise_for_status()
            path = _save("talmud", tractate, r.json())
            saved.append(path)
            ingest(f"talmud:{tractate}", send)
            time.sleep(0.5)
        except requests.RequestException as e:
            send(f"  Error fetching {tractate}: {e}")
    _cleanup_raw("talmud")
    return saved
def fetch_mormon(book: str | None = None, send: Callable[[str], None] = print) -> list[str]:
    if is_downloaded("mormon") and book is None:
        send("Book of Mormon already fully downloaded.")
        return []

    send("Fetching Book of Mormon...")
    try:
        r = requests.get(LIBRARY_CONFIG["mormon"]["base_url"], timeout=60)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        send(f"  Error fetching Book of Mormon: {e}")
        return []

    books_by_title = {b["book"]: b for b in data.get("books", [])}
    saved = []

    for registry_name in LIBRARY_BOOKS["mormon"]:
        if book and registry_name != book.lower():
            continue
        if is_downloaded("mormon", registry_name) and book is None:
            continue

        title = MORMON_TITLE_MAP.get(registry_name)
        if not title:
            send(f"  No title mapping for '{registry_name}'")
            continue

        book_data = books_by_title.get(title)
        if not book_data:
            send(f"  Could not find '{title}' in downloaded data")
            continue

        path = _save("mormon", registry_name, book_data)
        saved.append(path)
        ingest(f"mormon:{registry_name}", send)
    _cleanup_raw("mormon")
    return saved

def fetch_bible(book: str | None = None, send: Callable[[str], None] = print) -> list[str]:

    #Fetch one Bible book or the full KJV.
    #Returns list of saved file paths.

    cfg = LIBRARY_CONFIG["bible"]
    base = cfg["base_url"] 
    saved: list[str] = []

    if book is None:
        # Full Bible
        if is_downloaded("bible"):
            send("Bible is already fully downloaded.")
            return []

        send("Fetching full Bible (KJV)...")
        r = requests.get(f"{base}.json", timeout=60)
        r.raise_for_status()

        saved_path = _save("bible", "bible", r.json())
        saved.append(saved_path)
        ingest("bible", send)
        send(f"Bible download complete -> {saved_path}")

    else:
        # Single book
        book_key = book.lower().replace(" ", "")
        book_key = BOOK_NAME_REMAP.get(book_key, book_key)

        if not is_known("bible", book_key):
            msg = f"Unknown Bible book: '{book_key}'.\n"
            send(msg)
            raise ValueError(msg)

        if is_downloaded("bible", book_key):
            send(f"{book_key} is already downloaded.")
            return []

        num = BIBLE_BOOK_NUMS.get(book_key)
        if num is None:
            msg = f"Unknown Bible book: '{book_key}'"
            send(msg)
            raise ValueError(msg)

        send(f"Fetching Bible / {book_key} (book #{num})...")
        r = requests.get(f"{base}/{num}.json", timeout=30)
        r.raise_for_status()

        saved_path = _save("bible", book_key, r.json())
        saved.append(saved_path)
        ingest(f"bible:{book_key}", send)
        send(f"Book '{book_key}' download complete -> {saved_path}")
    _cleanup_raw("bible")
    return saved

# Fetch Arabic and English Quran and save both
def fetch_quran(send: Callable[[str], None] = print):
    if is_downloaded("quran"):
        send("Quran fully downloaded.")
        return

    cfg = LIBRARY_CONFIG["quran"]


    send("Fetching Quran (Arabic)...\n")

    r = requests.get(cfg["arabic_url"], timeout=60)
    r.raise_for_status()
    _save("quran", "arabic", r.json())
    send("Done fetching Quran in Arabic")

    time.sleep(1)  # rate limit

    send("Fetching Quran (English)...\n")
    r = requests.get(cfg["english_url"], timeout=60)
    r.raise_for_status()

    _save("quran", "english_asad", r.json())
    send("Done fetching Quran in English")
    ingest("quran",send) 
    _cleanup_raw("talmud")
    
def fetch(library: str, book: str | None = None, send: Callable[[str], None] = print) -> list[str]:
    # Entry point used by c download cmd and by ingest
    library = library.lower()
    if library == "bible":
        return fetch_bible(book, send)
    if library == "quran":
        return fetch_quran(send)
    if library == "talmud":
        return fetch_talmud(book, send)     
    if library == "hindu":
        return fetch_hindu(book, send)
    if library == "mormon":
        return fetch_mormon(book, send)
    return [f"Unsupported library: '{library}'"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: libquery download <library> [book]")
        sys.exit(1)
    _lib  = sys.argv[1]
    _book = sys.argv[2] if len(sys.argv) > 2 else None
    fetch(_lib, _book)
