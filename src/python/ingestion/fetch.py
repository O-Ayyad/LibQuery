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
import asyncio

from ingestion.ingest import ingest
from networking.registry import is_downloaded, is_known, LIBRARY_BOOKS

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import LIBRARY_CONFIG, RAW_DATA_DIR
from typing import Callable
import shutil


def _save(library: str, filename: str, data: dict) -> str: #Save the data to the raw data directory
    """Save a dict as JSON under data/raw/<library>/<filename>.json"""
    out_dir = os.path.join(RAW_DATA_DIR, library)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{filename}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {out_path}")
    return out_path

def cleanup_raw(library: str) -> None: #Clean up the raw data directory
    raw_dir = os.path.join(RAW_DATA_DIR, library)
    if os.path.isdir(raw_dir):
        shutil.rmtree(raw_dir)
        print(f"  Cleaned up {raw_dir}", flush=True)

# ________________________________________________________________________________________________ HINDU
# ________________________________________________________________________________________________ HINDU
# ________________________________________________________________________________________________ HINDU
def fetch_hindu(book: str | None = None, send: Callable[[str], None] = print) -> list[str]:
    saved: list[str] = []

    books_to_fetch = (
        [book.lower()] if book
        else [b for b in LIBRARY_BOOKS["hindu"] if not is_downloaded("hindu", b)]
    )

    if not books_to_fetch:
        send("Hindu texts are already fully downloaded.")
        return []

    ramayana_needed = [b for b in books_to_fetch if b.startswith("ramayana-")]
    non_ramayana = [b for b in books_to_fetch if not b.startswith("ramayana-")]

    if ramayana_needed:
        try:
            saved += _fetch_ramayana(ramayana_needed, send)
        except Exception as e:
            send(f"[hindu/ramayana] Error fetching Ramayana: {e}")

    for b in non_ramayana:
        try:
            if b == "bhagavadgita":
                saved += _fetch_gita(send)
            else:
                send(f"[hindu] Unknown hindu text: '{b}'")
        except Exception as e:
            send(f"  Error fetching {b}: {e}")

    book_arg = "hindu" if book is None else f"hindu:{book}"
    ingest(book_arg, send)  
    cleanup_raw("hindu")
    return saved

def _fetch_ramayana(kandas_needed: list[str], send: Callable[[str], None]) -> list[str]:
    base = LIBRARY_CONFIG["hindu"]["ramayanam_api_base"]
    url = f"{base}/slokas/slokas.csv"
    send("[hindu/ramayana] Fetching Valmiki Ramayana (full CSV)...")
    r = requests.get(url, timeout=120)
    r.raise_for_status()

    import csv, io
    reader = csv.DictReader(io.StringIO(r.text))

    #Split by kanda
    kandas: dict[int, list[dict]] = {}
    for row in reader:
        kanda = int(row["kanda"])
        kandas.setdefault(kanda, []).append(row)

    # Only ingest the kandas that were requested
    needed_nums = {int(b.split("-")[1]) for b in kandas_needed}

    saved = []
    for kanda_num, rows in sorted(kandas.items()):
        if kanda_num not in needed_nums:
            continue
        path = _save("hindu", f"ramayana-{kanda_num}", {"slokas": rows})
        saved.append(path)
        send(f"[hindu/ramayana] kanda {kanda_num} done ({len(rows)} slokas)")

    return saved

def _fetch_gita(send: Callable[[str], None]) -> list[str]:
    base = LIBRARY_CONFIG["hindu"]["dharmic_data_base"]
    send("[Hindu] Fetching Bhagavad Gita...")
    chapters = []
    for ch in range(1, 19):
        url = f"{base}/SrimadBhagvadGita/bhagavad_gita_chapter_{ch}.json"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        chapters.extend(r.json().get("BhagavadGitaChapter", []))
        send(f"[hindu/bhagvadgita] Fetched chapter {ch}")
        time.sleep(0.3)

    path = _save("hindu", "bhagavadgita", {"chapters": chapters})
    return [path]
#  _____________________________________________________________________________________________________ TALMUD
#  _____________________________________________________________________________________________________ TALMUD
# ______________________________________________________________________________________________________ TALMUD

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

def fetch_talmud(book: str | None = None, send: Callable[[str], None] = print) -> list[str]:
    saved: list[str] = []
    base_url = LIBRARY_CONFIG["talmud"]["base_url"]

    books_to_fetch = (
        [book.lower()] if book
        else [b for b in LIBRARY_BOOKS["talmud"] if not is_downloaded("talmud", b)]
    )

    if not books_to_fetch:
        send("Talmud is already fully downloaded.")
        return []

    for tractate in books_to_fetch:
        sefaria_ref = TALMUD_SEFARIA_REFS.get(tractate)
        if not sefaria_ref:
            send(f"Unknown tractate: '{tractate}'")
            send(f"[talmud] Available: {', '.join(sorted(TALMUD_SEFARIA_REFS.keys()))}")
            continue
        send(f"[Talmud] Fetching talmud/{tractate}...")
        try:
            data = _fetch_talmud_tractate(base_url, tractate, sefaria_ref, send)
            path = _save("talmud", tractate, data)
            saved.append(path)
            time.sleep(0.5)
        except requests.RequestException as e:
            raise ValueError(f"  Error fetching {tractate}: {e}")
        
    book_arg = "talmud" if book is None else f"talmud:{book}"
    ingest(book_arg, send)
    cleanup_raw("talmud")
    return saved


def _fetch_talmud_tractate(base_url: str, tractate: str, sefaria_ref: str, send: Callable[[str], None]) -> dict:
    #try fetching the whole tractate
    r = requests.get(
        f"{base_url}/{sefaria_ref}",
        params={"lang": "bi", "pad": 0, "context": 0},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()

    # If spanning fetch daf by daf and merge
    if data.get("isSpanning") or data.get("spanning"):
        send(f"[talmud] {tractate} is spanning — fetching by daf...")
        all_en, all_he = [], []
        daf_letters = ["a", "b"]
        # Talmud dafs start at 2
        for daf_num in range(2, 200):
            for letter in daf_letters:
                ref = f"{sefaria_ref}.{daf_num}{letter}"
                try:
                    r2 = requests.get(
                        f"{base_url}/{ref}",
                        params={"lang": "bi", "pad": 0, "context": 0},
                        timeout=30,
                    )
                    r2.raise_for_status()
                    daf_data = r2.json()
                    if not daf_data.get("text") and not daf_data.get("he"):
                        return {"text": all_en, "he": all_he}
                    all_en.append(daf_data.get("text", []))
                    all_he.append(daf_data.get("he", []))
                    time.sleep(0.3)
                except requests.RequestException:
                    return {"text": all_en, "he": all_he}
        return {"text": all_en, "he": all_he}

    return data

#  _____________________________________________________________________________________________________ MORMON
#  _____________________________________________________________________________________________________ MORMON
# ______________________________________________________________________________________________________ MORMON

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

def fetch_mormon(book: str | None = None, send: Callable[[str], None] = print) -> list[str]:
    if is_downloaded("mormon") and book is None:
        send("Book of Mormon already fully downloaded.")
        return []

    send("[mormon] Fetching Book of Mormon...")
    try:
        r = requests.get(LIBRARY_CONFIG["mormon"]["base_url"], timeout=60)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise ValueError(f"  Error fetching Book of Mormon: {e}")

    books_by_title = {b["book"]: b for b in data.get("books", [])}
    saved = []

    for registry_name in LIBRARY_BOOKS["mormon"]:
        if book and registry_name != book.lower():
            continue
        if is_downloaded("mormon", registry_name) and book is None:
            continue

        title = MORMON_TITLE_MAP.get(registry_name)
        if not title:
            send(f"[mormon] No title mapping for '{registry_name}'")
            continue

        book_data = books_by_title.get(title)
        if not book_data:
            send(f"[mormon] Could not find '{title}' in downloaded data")
            continue

        path = _save("mormon", registry_name, book_data)
        saved.append(path)

    book_arg = "mormon" if book is None else f"mormon:{book}"
    ingest(book_arg, send)  
    cleanup_raw("mormon")
    return saved

#  _____________________________________________________________________________________________________ BIBLE
#  _____________________________________________________________________________________________________ BIBLE
# ______________________________________________________________________________________________________ BIBLE

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

        send("[bible] Fetching full Bible (KJV)...")
        r = requests.get(f"{base}.json", timeout=60)
        r.raise_for_status()

        saved_path = _save("bible", "bible", r.json())
        saved.append(saved_path)
        send(f"[bible] Bible download complete")

    else:
        # Single book
        book_key = book.lower().replace(" ", "")
        book_key = BOOK_NAME_REMAP.get(book_key, book_key)

        if not is_known("bible", book_key):
            msg = f"[bible] Unknown Bible book: '{book_key}'.\n"
            send(msg)
            raise ValueError(msg)

        if is_downloaded("bible", book_key):
            send(f"{book_key} is already downloaded.")
            return []

        num = BIBLE_BOOK_NUMS.get(book_key)
        if num is None:
            msg = f"[bible] Unknown Bible book: '{book_key}'"
            send(msg)
            raise ValueError(msg)

        send(f"[bible] Fetching Bible / {book_key} (book #{num})...")
        r = requests.get(f"{base}/{num}.json", timeout=30)
        r.raise_for_status()

        saved_path = _save("bible", book_key, r.json())
        saved.append(saved_path)
        send(f"[bible] Book '{book_key}' download complete")
    book_arg = "bible" if book is None else f"bible:{book}"
    ingest(book_arg, send)  
    cleanup_raw("bible")
    return saved
#  _____________________________________________________________________________________________________ QURAN
#  _____________________________________________________________________________________________________ QURAN
# ______________________________________________________________________________________________________ QURAN

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

# Fetch Arabic and English Quran and save both
def fetch_quran(book: str |None = None, send: Callable[[str], None] = print) -> list[str]: #book for dispatch
    if is_downloaded("quran"):
        send("[quran] Quran fully downloaded.")
        return []

    cfg = LIBRARY_CONFIG["quran"]


    send("[quran] Fetching Quran (Arabic)...\n")

    r = requests.get(cfg["arabic_url"], timeout=60)
    r.raise_for_status()
    path_ar = _save("quran", "arabic", r.json())
    send("[quran] Done fetching Quran in Arabic")

    time.sleep(1)  # rate limit

    send("[quran] Fetching Quran (English)...\n")
    r = requests.get(cfg["english_url"], timeout=60)
    r.raise_for_status()

    path_en = _save("quran", "english_asad", r.json())
    send("[quran] Done fetching Quran in English") 

    ingest("quran", send)
    cleanup_raw("quran")
    return [path_ar, path_en]

#  _____________________________________________________________________________________________________ SHAKESPEARE
#  _____________________________________________________________________________________________________ SHAKESPEARE
# ______________________________________________________________________________________________________ SHAKESPEARE

SHAKESPEARE_PLAYS = {
    "allswell": "All's Well That Ends Well",
    "asyoulikeit": "As You Like It",
    "comedy_errors": "Comedy of Errors",
    "cymbeline": "Cymbeline",
    "lll": "Love's Labour's Lost",
    "measure": "Measure for Measure",
    "merchant":  "Merchant of Venice",
    "merry_wives": "Merry Wives of Windsor",
    "midsummer":  "A Midsummer Night's Dream",
    "much_ado": "Much Ado About Nothing",
    "pericles": "Pericles",
    "taming_shrew": "Taming of the Shrew",
    "tempest":  "The Tempest",
    "troilus_cressida": "Troilus and Cressida",
    "twelfth_night": "Twelfth Night",
    "two_gentlemen": "Two Gentlemen of Verona",
    "winters_tale": "The Winter's Tale",
    "cleopatra": "Antony and Cleopatra",
    "coriolanus": "Coriolanus",
    "hamlet": "Hamlet",
    "julius_caesar": "Julius Caesar",
    "lear": "King Lear",
    "macbeth":"Macbeth",
    "othello":"Othello",
    "romeo_juliet": "Romeo and Juliet",
    "timon": "Timon of Athens",
    "titus": "Titus Andronicus",
    "1henryiv": "Henry IV Part 1",
    "2henryiv": "Henry IV Part 2",
    "henryv":"Henry V",
    "1henryvi": "Henry VI Part 1",
    "2henryvi": "Henry VI Part 2",
    "3henryvi": "Henry VI Part 3",
    "henryviii": "Henry VIII",
    "john":"King John",
    "richardii": "Richard II",
    "richardiii":"Richard III",
}

def fetch_shakespeare(book: str | None = None, send: Callable[[str], None] = print) -> list[str]:
    from bs4 import BeautifulSoup

    plays_to_fetch = (
        [book.lower()] if book
        else [s for s in SHAKESPEARE_PLAYS if not is_downloaded("shakespeare", s)]
    )

    if not plays_to_fetch:
        send("Shakespeare is already fully downloaded.")
        return []

    saved = []
    for play in plays_to_fetch:
        if play not in SHAKESPEARE_PLAYS:
            send(f"[shakespeare] Unknown play: '{play}'")
            continue
        
        _url_1 = LIBRARY_CONFIG["shakespeare"]["base_url_part1"]
        _url_2 = LIBRARY_CONFIG["shakespeare"]["base_url_part2"]
        
        url = _url_1 + play + _url_2

        send(f"[shakespeare] Fetching {SHAKESPEARE_PLAYS[play]}...")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            send(f"[shakespeare] Error fetching {play}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        lines = []

        for tag in soup.find_all(["h3", "b", "blockquote"]):
            if tag.name == "h3":
                lines.append({"tag": "h3", "text": tag.get_text(strip=True)})
            elif tag.name == "b":
                lines.append({"tag": "b", "text": tag.get_text(strip=True)})
            elif tag.name == "blockquote":
                if tag.find("i") and not tag.get_text(strip=True).replace(
                    tag.find("i").get_text(strip=True), ""
                ).strip():
                    continue
                for line in tag.get_text("\n").splitlines():
                    line = line.strip()
                    if line:
                        lines.append({"tag": "line", "text": line})

        path = _save("shakespeare", play, {"slug": play, "lines": lines})
        saved.append(path)
        time.sleep(0.5)

    book_arg = "shakespeare" if book is None else f"shakespeare:{book}"
    ingest(book_arg, send)  
    cleanup_raw("shakespeare")
    return saved

def download_full_library(lib: str, send: Callable[[str], None]) -> list[str]:
    send(f"[{lib}] starting full download")

    try:
        saved = libquery_dispatch(lib, None, send)

        if not saved:
            send(f"[fetch {lib}] WARNING: nothing was downloaded")
            return []

        send(f"[fetch {lib}] finished ({len(saved)} files)")
        return saved

    except Exception as e:
        send(f"[fetch {lib}] ERROR: {e}")
        return []


async def download_all(send: Callable[[str], None] = print):
    from concurrent.futures import ThreadPoolExecutor

    loop = asyncio.get_running_loop()
    libs = list(LIBRARY_DISPATCH.keys())

    with ThreadPoolExecutor(max_workers=len(libs)) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                download_full_library,
                lib,
                send
            )
            for lib in libs
        ]

        return await asyncio.gather(*tasks)

LIBRARY_DISPATCH: dict[str, Callable[..., list[str]]] = {}

LIBRARY_DISPATCH = {
    "bible": fetch_bible,
    "quran": fetch_quran,
    "talmud": fetch_talmud,
    "hindu": fetch_hindu,
    "mormon": fetch_mormon,
    "shakespeare": fetch_shakespeare,
}

def libquery_dispatch(
    library: str,
    book: str | None = None,
    send: Callable[[str], None] = print
) -> list[str]:

    library = library.lower()

    if library == "all":
        return download_full_library(send)

    handler = LIBRARY_DISPATCH.get(library)

    if not handler:
        raise ValueError(
            f"Unsupported library '{library}'. Available: {list(LIBRARY_DISPATCH.keys())}"
        )

    return handler(book, send)
def fetch(library: str, book: str | None = None, send=print) -> bool:
    
    library = library.lower()
    if library == "all":
        import asyncio
        asyncio.run(download_all(send))
        return True
    return libquery_dispatch(library, book, send)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: libquery download <library> [book]")
        sys.exit(1)
    _lib  = sys.argv[1]
    _book = sys.argv[2] if len(sys.argv) > 2 else None
    fetch(_lib, _book)
