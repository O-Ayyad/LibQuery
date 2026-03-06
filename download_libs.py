
import sys
import json
import time
import requests

def book_to_num(_book) -> int:
    BOOK_NUMS = {
        "genesis": 1,
        "exodus": 2,
        "leviticus": 3,
        "numbers": 4,
        "deuteronomy": 5,
        "joshua": 6,
        "judges": 7,
        "ruth": 8,
        "1 samuel": 9,
        "2 samuel": 10,
        "1 kings": 11,
        "2 kings": 12,
        "1 chronicles": 13,
        "2 chronicles": 14,
        "ezra": 15,
        "nehemiah": 16,
        "esther": 17,
        "job": 18,
        "psalms": 19,
        "proverbs": 20,
        "ecclesiastes": 21,
        "song of solomon": 22,
        "isaiah": 23,
        "jeremiah": 24,
        "lamentations": 25,
        "ezekiel": 26,
        "daniel": 27,
        "hosea": 28,
        "joel": 29,
        "amos": 30,
        "obadiah": 31,
        "jonah": 32,
        "micah": 33,
        "nahum": 34,
        "habakkuk": 35,
        "zephaniah": 36,
        "haggai": 37,
        "zechariah": 38,
        "malachi": 39,
        "matthew": 40,
        "mark": 41,
        "luke": 42,
        "john": 43,
        "acts": 44,
        "romans": 45,
        "1 corinthians": 46,
        "2 corinthians": 47,
        "galatians": 48,
        "ephesians": 49,
        "philippians": 50,
        "colossians": 51,
        "1 thessalonians": 52,
        "2 thessalonians": 53,
        "1 timothy": 54,
        "2 timothy": 55,
        "titus": 56,
        "philemon": 57,
        "hebrews": 58,
        "james": 59,
        "1 peter": 60,
        "2 peter": 61,
        "1 john": 62,
        "2 john": 63,
        "3 john": 64,
        "jude": 65,
        "revelation": 66,
        }
    if _book.lower() not in BOOK_NUMS:
        print(f"'{_book}' is not a valid book name")
        return -1
    
    return BOOK_NUMS.get(_book.lower())

def download_bible(_entireLibrary, _book):
    print("Downloading Bible")
    booknum = 0
    bible_url = ""

    if _entireLibrary:
        bible_url = f"https://api.getbible.net/v2/kjv.json"
    else:
        booknum = book_to_num(_book) # booknum is 1 for genesis, 2 for exodus to 66
        if booknum == -1:
            return
        
        bible_url = f"https://api.getbible.net/v2/kjv/{booknum}.json" 
        
    response = requests.get(bible_url)
    response.raise_for_status()
    
    with open("bible.json", "w", encoding="utf-8") as f:
        json.dump(response.json(), f, indent=2)
    print("Saved to bible.json")
    #TODO: Parse to csv

def download_quran(): #merge arabic and english into csv
    print("Downloading Quran")
    quran_url = "https://api.alquran.cloud/v1/quran/quran-uthmani"
    translated_url = "https://api.alquran.cloud/v1/quran/en.asad"

    response = requests.get(quran_url)
    response.raise_for_status()
    
    with open("quran_arabic.json", "w", encoding="utf-8") as f:
        json.dump(response.json(), f, indent=2)
    print("Saved to quran_arabic.json")

    time.sleep(1000)
    response = requests.get(translated_url)
    response.raise_for_status()
    
    with open("quran_english.json", "w", encoding="utf-8") as f:
        json.dump(response.json(), f, indent=2)
    print("Saved to quran_english.json")

library = sys.argv[1] #library  
book    = sys.argv[2] #book
entireLibrary = (book == "download_entire_library")

match library:
    case "bible":
        download_bible(entireLibrary, book)
        pass
    case "quran":
        download_quran()
        pass
    case _:
        print(f"Unknown library: {library}")