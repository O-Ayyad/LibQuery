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


'''
    libquery alias bible b adds "b":"bible" to dictionary
    libquery b genesis 1:1 is valid

    libquery alias bible genesis g
    libquery b g 1:1 is now valid

    libquery alias ls lists all current aliases
    libquery alias rm <alias> or all removes aliases

'''
LIBRARY_ALIASES = { 
    

}
LIBRARY_CONFIG = {
    "bible": {
        "base_url": "https://api.getbible.net/v2/kjv",
        "translation": "kjv",
        "format":"getbible",   #tells ingest which json shape to expect
    },
    "quran": {
        "arabic_url":  "https://api.alquran.cloud/v1/quran/quran-uthmani",
        "english_url": "https://api.alquran.cloud/v1/quran/en.asad",
        "format": "alquran",
    },
}
