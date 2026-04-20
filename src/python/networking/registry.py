# networking/registry.py

from __future__ import annotations
import os
import sys

sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".."))
from config.storage import isdir, has_parquet, library_path, book_path

LIBRARY_BOOKS: dict[str, list[str]] = {
    "bible": [
        "genesis", "exodus", "leviticus", "numbers", "deuteronomy",
        "joshua", "judges", "ruth", "1samuel", "2samuel",
        "1kings", "2kings", "1chronicles", "2chronicles", "ezra",
        "nehemiah", "esther", "job", "psalms", "proverbs",
        "ecclesiastes", "songofsongs", "isaiah", "jeremiah", "lamentations",
        "ezekiel", "daniel", "hosea", "joel", "amos",
        "obadiah", "jonah", "micah", "nahum", "habakkuk",
        "zephaniah", "haggai", "zechariah", "malachi", "matthew",
        "mark", "luke", "john", "acts", "romans",
        "1corinthians", "2corinthians", "galatians", "ephesians", "philippians",
        "colossians", "1thessalonians", "2thessalonians", "1timothy", "2timothy",
        "titus", "philemon", "hebrews", "james", "1peter",
        "2peter", "1john", "2john", "3john", "jude", "revelation",
    ],
    "quran": [
        "al-faatiha", "al-baqara", "aal-i-imraan", "an-nisaa", "al-maaida",
        "al-anaam", "al-araaf", "al-anfaal", "at-tawba", "yunus",
        "hud", "yusuf", "ar-rad", "ibrahim", "al-hijr",
        "an-nahl", "al-israa", "al-kahf", "maryam", "taa-haa",
        "al-anbiyaa", "al-hajj", "al-muminoon", "an-noor", "al-furqaan",
        "ash-shuaraa", "an-naml", "al-qasas", "al-ankaboot", "ar-room",
        "luqman", "as-sajda", "al-ahzaab", "saba", "faatir",
        "yaseen", "as-saaffaat", "saad", "az-zumar", "ghafir",
        "fussilat", "ash-shura", "az-zukhruf", "ad-dukhaan", "al-jaathiya",
        "al-ahqaf", "muhammad", "al-fath", "al-hujuraat", "qaaf",
        "adh-dhaariyat", "at-tur", "an-najm", "al-qamar", "ar-rahmaan",
        "al-waaqia", "al-hadid", "al-mujaadila", "al-hashr", "al-mumtahana",
        "as-saff", "al-jumua", "al-munaafiqoon", "at-taghaabun", "at-talaaq",
        "at-tahrim", "al-mulk", "al-qalam", "al-haaqqa", "al-maaarij",
        "nooh", "al-jinn", "al-muzzammil", "al-muddaththir", "al-qiyaama",
        "al-insaan", "al-mursalaat", "an-naba", "an-naaziaat", "abasa",
        "at-takwir", "al-infitaar", "al-mutaffifin", "al-inshiqaaq", "al-burooj",
        "at-taariq", "al-alaa", "al-ghaashiya", "al-fajr", "al-balad",
        "ash-shams", "al-lail", "ad-dhuhaa", "ash-sharh", "at-tin",
        "al-alaq", "al-qadr", "al-bayyina", "az-zalzala", "al-aadiyaat",
        "al-qaaria", "at-takaathur", "al-asr", "al-humaza", "al-fil",
        "quraish", "al-maaun", "al-kawthar", "al-kaafiroon", "an-nasr",
        "al-masad", "al-ikhlaas", "al-falaq", "an-naas",
    ],
    
    "hindu": [
        
        "bhagavadgita",
        
        "ramayana-1", "ramayana-2", "ramayana-3",
        "ramayana-4", "ramayana-5", "ramayana-6",
    ],

    "talmud": [
        "berakhot","shabbat", "eruvin", "pesachim", "yoma", "sukkah",
        "beitzah", "rosh-hashanah", "taanit", "megillah", "moed-katan", "chagigah",
        "yevamot", "ketubot", "nedarim", "nazir", "sotah", "gittin", "kiddushin",
        "bava-kamma", "bava-metzia", "bava-batra", "sanhedrin", "makkot",
        "shevuot", "avodah-zarah", "horayot", "zevachim", "menachot", "chullin",
        "bekhorot", "arakhin", "temurah", "keritot", "meilah", "tamid", "niddah",
    ],
    "mormon": [
        "1nephi", "2nephi", "jacob", "enos", "jarom", "omni",
        "wordsofmormon", "mosiah", "alma", "helaman",
        "3nephi", "4nephi", "mormon", "ether", "moroni",
    ],
}
    
_downloaded_cache: dict[str, set[str]] = {}

def _book_on_disk(library: str, book: str) -> bool:

    if library in _downloaded_cache:
        return book in _downloaded_cache[library]

    return has_parquet(book_path(library, book))

def is_downloaded(library: str, book: str | None = None) -> bool:

    if library not in LIBRARY_BOOKS:
        return False
    if book is None:
        return all(_book_on_disk(library, b) for b in LIBRARY_BOOKS[library])
    return _book_on_disk(library, book)


def is_known(library: str, book: str) -> bool:
    return library in LIBRARY_BOOKS and book in LIBRARY_BOOKS[library]


def missing_books(library: str) -> list[str]:
    #Return list of books not yet on disk
    if library not in LIBRARY_BOOKS:
        return []
    return [b for b in LIBRARY_BOOKS[library] if not _book_on_disk(library, b)]


def downloaded_books(library: str) -> list[str]:
    if library not in LIBRARY_BOOKS:
        return []
    return [b for b in LIBRARY_BOOKS[library] if _book_on_disk(library, b)]


def known_libraries() -> list[str]:
    return list(LIBRARY_BOOKS.keys())


def known_books(library: str) -> list[str]:
    #Return all known books for a library downloaded or not.
    return LIBRARY_BOOKS.get(library, [])

def scan_downloaded_books(): #Scan dirs to see which books exist
    global _downloaded_cache
    _downloaded_cache = {}
    for library in LIBRARY_BOOKS:
        lib_path = library_path(library)
        if not isdir(lib_path):
            _downloaded_cache[library] = set()
            continue
        _downloaded_cache[library] = {
            b for b in LIBRARY_BOOKS[library]
            if has_parquet(book_path(library, b))
        }

def ls(library :str |None = None) -> str: #List all books and download status
    
    scan_downloaded_books() 
    if not library:
        lines = []
        for lib, books in LIBRARY_BOOKS.items():
            done = len(downloaded_books(lib))
            total = len(books)
            lines.append(f"{lib}: {done}/{total} downloaded")
        return "\n".join(lines)

    library = library.strip().lower()
       
    if library not in LIBRARY_BOOKS:
        libs = ", ".join(known_libraries())
        return f"[registry] Unknown library '{library}'. Available: {libs}"

    books = LIBRARY_BOOKS[library]
    done = len(downloaded_books(library))

    lines = [
        f"{library}: {done}/{len(books)} downloaded",
        "-" * 40
    ]

    for book in books:
        status = "YES" if is_downloaded(library, book) else "NO"
        lines.append(f"  {status}  {book}")

    return "\n".join(lines)