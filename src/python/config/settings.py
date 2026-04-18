import os
from dotenv import load_dotenv

# Paths
_HERE= os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")

load_dotenv()
class EnvConfigs:
    def __init__(self):

        self.HOST = os.getenv("LIBQUERY_HOST", "0.0.0.0")
        self.PORT = int(os.getenv("LIBQUERY_PORT", "9237"))
        self.MAX_CONCURRENT_QUERIES = int(os.getenv("LIBQUERY_MAX_CONNS", "100"))

        self.SPARK_MASTER = os.getenv("LIBQUERY_SPARK_MASTER", "local[*]")
        self.SPARK_APP = "libquery"

        self.USE_HDFS = os.getenv("LIBQUERY_USE_HDFS", "false").lower() == "true"
        self.HDFS_HOST = os.getenv("LIBQUERY_HDFS_HOST", "localhost")
        self.HDFS_PORT = int(os.getenv("LIBQUERY_HDFS_PORT", "9000"))
        self.HDFS_USER = os.getenv("LIBQUERY_HDFS_USER") or None
        
        _default_parquet = (
            "/libquery/parquet"
            if self.USE_HDFS
            else os.path.join(PROJECT_ROOT, "data", "parquet")
        )

        self.PARQUET_DIR = os.getenv("LIBQUERY_PARQUET_DIR", _default_parquet)

def get_configs()-> EnvConfigs:
    return EnvConfigs()

config = EnvConfigs()

# Server
HOST = config.HOST
PORT = config.PORT
MAX_CONCURRENT_QUERIES = config.MAX_CONCURRENT_QUERIES

# Spark
SPARK_MASTER = config.SPARK_MASTER
SPARK_APP = config.SPARK_APP


#HDFS
USE_HDFS = config.USE_HDFS
HDFS_HOST = config.HDFS_HOST
HDFS_PORT = config.HDFS_PORT
HDFS_USER = config.HDFS_USER

PARQUET_DIR = config.PARQUET_DIR

# Library configurations and API endpoints
LIBRARY_CONFIG = {
    "bible": {
        "base_url": "https://api.getbible.net/v2/kjv",
    },
    "quran": {
        "arabic_url":  "https://api.alquran.cloud/v1/quran/quran-uthmani",
        "english_url": "https://api.alquran.cloud/v1/quran/en.asad",
    },    
    "talmud": {
        "base_url": "https://www.sefaria.org/api/texts",
    },
    "hindu": {
        "dharmic_data_base": "https://raw.githubusercontent.com/bhavykhatri/DharmicData/main",
        "ramayanam_api_base": "https://raw.githubusercontent.com/imradhe/ramayanam-api/main",
    },
    "mormon": {
        "base_url": "https://raw.githubusercontent.com/BraydenTW/book-of-mormon-api/refs/heads/main/book-of-mormon.json",
    },
}
