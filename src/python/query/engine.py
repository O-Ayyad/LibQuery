from __future__ import annotations
import os
import sys
from typing import Any
from pyspark.sql import SparkSession

#Allows a single execute(payload) -> list[dict] function that the server calls
#The payload is the same as what main.c sends over the socket

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import SPARK_MASTER, SPARK_APP, PARQUET_DIR
from query.sql_builder import build_query, NO_VERSE

_spark = None

def _get_spark():
    global _spark
    if _spark is None:
        _spark = (
            SparkSession.builder
            .master(SPARK_MASTER)
            .appName(SPARK_APP)
            .config("spark.sql.parquet.filterPushdown",  "true")
            .config("spark.sql.parquet.mergeSchema", "false")
            .config("spark.ui.showConsoleProgress", "false")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.driver.extraJavaOptions", "-Dlog4j.configuration=log4j2.properties")
            .getOrCreate()
        )
        _spark.sparkContext.setLogLevel("ERROR")
    return _spark

def _load_book(spark, library: str, book: str,chapter: int = None) -> None:

    if library == "quran" and book == "quran":
        from ingestion.fetch import QURAN_SURAHS
        if chapter is None or chapter not in QURAN_SURAHS:
            raise ValueError(f"Unknown surah number: {chapter}")
        surah = QURAN_SURAHS[chapter]
        book_dir = os.path.join(PARQUET_DIR, library, surah)
    else:
        book_dir = os.path.join(PARQUET_DIR, library, book)

    if not os.path.exists(book_dir):
        print("DEBUG BOOK DIR:", book_dir)
        raise FileNotFoundError(
            f"No data for {library}/{book}. "
            f"Run: libquery download {library} {book}"
        )
    df = spark.read.parquet(book_dir)
    df.createOrReplaceTempView("library")

def execute(payload: dict[str, Any]) -> list[dict]:
    print(payload)
    library       = payload["library"].lower()
    book          = payload["book"].lower()
    start_chapter = int(payload["start_chapter"])
    start_verse   = int(payload.get("start_verse",  NO_VERSE))
    end_chapter   = int(payload.get("end_chapter",  start_chapter))
    end_verse     = int(payload.get("end_verse",    NO_VERSE))
    lang          = payload.get("lang", "en")

    spark = _get_spark()
    _load_book(spark, library, book, chapter=start_chapter,)

    sql = build_query(
        library, book,
        start_chapter=start_chapter,
        start_verse=start_verse,
        end_chapter=end_chapter,
        end_verse=end_verse,
        lang=lang,
    )

    rows = spark.sql(sql).collect()
    return [{"chapter": r["chapter"], "verse": r["verse"], "text": r["text"]}
            for r in rows if r["text"].strip()]
