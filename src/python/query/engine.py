from __future__ import annotations
import os
import sys
from typing import Any
from pyspark.sql import SparkSession, dataframe
import json
import uuid

#Allows a single execute(payload) -> list[dict] function that the server calls
#The payload is the same as what main.c sends over the socket

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import SPARK_MASTER, SPARK_APP, PARQUET_DIR
from query.sql_builder import build_query, NO_VERSE
from networking.registry import LIBRARY_BOOKS, is_downloaded

_spark: SparkSession | None = None

_QURAN_SURAHS: dict[int, str] = {i: name for i, name in enumerate(LIBRARY_BOOKS["quran"], 1)}

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
def _load_books(spark: SparkSession, 
                library: str, book: str, 
                start_chapter: int, end_chapter: int) -> dataframe:

    if library == "quran":
        dirs_to_load: list[str] = []
        for surah_num in range(start_chapter, end_chapter + 1):
            surah_name = _QURAN_SURAHS.get(surah_num)
            if surah_name is None:
                raise ValueError(f"Unknown surah number: {surah_num}")
            book_dir = os.path.join(PARQUET_DIR, library, surah_name)
            if not os.path.exists(book_dir):
                raise FileNotFoundError(
                    f"Surah {surah_num} ({surah_name}) not found.\n"
                    f"Run: libquery download quran"
                )
            dirs_to_load.append(book_dir)
        return spark.read.parquet(*dirs_to_load)

    book_dir = os.path.join(PARQUET_DIR, library, book)
    if not os.path.exists(book_dir):
        raise FileNotFoundError(
            f"No data for {library}/{book}.\n"
            f"Run: libquery download {library} {book}"
        )
    return spark.read.parquet(book_dir)

def execute(payload: dict[str, Any]) -> list[dict]: # Payload builds SQL query then returns rows to CLI
    print("Executing payload:", json.dumps(payload, indent=2))
    library       = payload["library"].lower()
    book          = payload["book"].lower()
    start_chapter = int(payload.get("start_chapter", 1))
    start_verse   = int(payload.get("start_verse",  NO_VERSE))
    end_chapter   = int(payload.get("end_chapter",  start_chapter))
    end_verse     = int(payload.get("end_verse",    NO_VERSE))
    lang          = payload.get("lang", None)

    if library == "quran": #Quran has no books edge case
        for surah_num in range(start_chapter, end_chapter + 1):
            surah_name = _QURAN_SURAHS.get(surah_num)
            if not surah_name or not is_downloaded("quran", surah_name):
                raise FileNotFoundError(
                    f"Surah {surah_num} not found.\n"
                    f"Run: libquery download quran"
                )
    else:
        if not is_downloaded(library, book):
            raise FileNotFoundError(
                f"No data for {library}/{book}.\n"
                f"Run: libquery download {library} {book}"
            )

    spark = _get_spark()
    df = _load_books(spark, library, book, start_chapter, end_chapter)

    view_name = f"libq_{uuid.uuid4().hex}"
    try:
        df.createTempView(view_name)

        sql = build_query(
            library,
            view_name=view_name,
            start_chapter=start_chapter,
            start_verse=start_verse,
            end_chapter=end_chapter,
            end_verse=end_verse,
            lang=lang,
        )

        rows = spark.sql(sql).collect()
    finally:
        spark.catalog.dropTempView(view_name)

    return [
        {"chapter": r["chapter"], "verse": r["verse"], "text": r["text"], "lang": r["lang"]}
        for r in rows if r["text"].strip()
    ]
