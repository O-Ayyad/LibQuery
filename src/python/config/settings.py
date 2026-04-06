import os

# Server
HOST = os.getenv("LIBQUERY_HOST", "0.0.0.0")
PORT = int(os.getenv("LIBQUERY_PORT", "9237"))
MAX_CONCURRENT_QUERIES = int(os.getenv("LIBQUERY_MAX_CONNS", "100"))

# Spark
SPARK_MASTER = os.getenv("LIBQUERY_SPARK_MASTER", "local[*]")
SPARK_APP = "libquery"

# Paths
_HERE= os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
PARQUET_DIR = os.path.join(PROJECT_ROOT, "data", "parquet")

# Library configurations and API endpoints
LIBRARY_CONFIG = {
    "bible": {
        "base_url": "https://api.getbible.net/v2/kjv",
        "translation": "kjv",
    },
    "quran": {
        "arabic_url":  "https://api.alquran.cloud/v1/quran/quran-uthmani",
        "english_url": "https://api.alquran.cloud/v1/quran/en.asad",
    },    
    "talmud": {
        "base_url": "https://www.sefaria.org/api/texts",
    },
    "hindu": {
        "gita_base":         "https://bhagavadgita.theaum.org",
        "dharmic_data_base": "https://raw.githubusercontent.com/bhavykhatri/DharmicData/main",
        "upanishads_base":   "https://raw.githubusercontent.com/vedicscriptures/upanishads/main",

    },
    "mormon": {
        "base_url": "https://raw.githubusercontent.com/BraydenTW/book-of-mormon-api/refs/heads/main/book-of-mormon.json",
    },
}
