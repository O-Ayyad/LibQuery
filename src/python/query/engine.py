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
from networking.registry import LIBRARY_BOOKS, is_downloaded

_spark: SparkSession | None = None

def _get_spark() -> SparkSession:
    global _spark
    if _spark is None:
        _spark = (SparkSession.builder
            .appName("LibQuery")
            .config("spark.driver.extraJavaOptions",
                    "-Dlog4j2.configurationFile=log4j2.properties"
                    " --add-opens=java.base/sun.nio.ch=ALL-UNNAMED")
            .getOrCreate())
    return _spark

def _load_book(spark, library: str, book: str,start_chapter: int = None) -> None:

    if library == "quran":
        from ingestion.fetch import QURAN_SURAHS
        surahs = {i: name for i, name in enumerate(LIBRARY_BOOKS["quran"], 1)}
        if start_chapter is None or start_chapter not in surahs:
            raise ValueError(f"Unknown surah number: {start_chapter}")
        book_dir = os.path.join(PARQUET_DIR, library, surahs[start_chapter])
    else:
        book_dir = os.path.join(PARQUET_DIR, library, book)

    if not os.path.exists(book_dir):
        raise FileNotFoundError(
            f"No data for {library}/{book}. \n"
            f"Run: libquery download {library} {book}"
        )
    spark.read.parquet(book_dir).createOrReplaceTempView("library")

def execute(payload: dict[str, Any]) -> list[dict]:
    print(payload)
    library       = payload["library"].lower()
    book          = payload["book"].lower()
    start_chapter = int(payload.get("start_chapter", 1))
    start_verse   = int(payload.get("start_verse",  NO_VERSE))
    end_chapter   = int(payload.get("end_chapter",  start_chapter))
    end_verse     = int(payload.get("end_verse",    NO_VERSE))
    lang          = payload.get("lang", "en")

    if library == "quran":
        surahs = {i: name for i, name in enumerate(LIBRARY_BOOKS["quran"], 1)}
        book_name = surahs.get(start_chapter)
        if not book_name or not is_downloaded("quran", book_name):
            raise FileNotFoundError(
                f"Surah {start_chapter} not found.\n"
                f"Run: libquery download quran"
            )
    else:
        if not is_downloaded(library, book):
            raise FileNotFoundError(
                f"No data for {library}/{book}.\n"
                f"Run: libquery download {library} {book}"
            )
        
    spark = _get_spark()
    _load_book(spark, library, book, start_chapter=start_chapter,)

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
