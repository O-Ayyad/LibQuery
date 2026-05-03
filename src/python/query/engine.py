from __future__ import annotations
import os
import sys
import uuid
from typing import Any
from pyspark.sql import SparkSession, DataFrame
import json

#Allows a single execute(payload) -> list[dict] function that the server calls
#The payload is the same as what main.c sends over the socket

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import SPARK_MASTER, SPARK_APP, USE_HDFS, HDFS_HOST, HDFS_PORT
from config.storage import isdir, book_path
from query.sql_builder import build_query, NO_VERSE
from networking.registry import LIBRARY_BOOKS, is_downloaded

_spark: SparkSession | None = None

_QURAN_SURAHS: dict[int, str] = {i: name for i, name in enumerate(LIBRARY_BOOKS["quran"], 1)}

def _get_spark() -> SparkSession:
    global _spark
    if _spark is None:
        builder = (SparkSession.builder
            .appName("LibQuery")
            .master(SPARK_MASTER)
            .config("spark.driver.extraJavaOptions",
                    "-Dlog4j2.configurationFile=log4j2.properties"
                    " --add-opens=java.base/sun.nio.ch=ALL-UNNAMED"))

        if USE_HDFS:
            builder = builder \
                .config("spark.hadoop.fs.defaultFS", f"hdfs://{HDFS_HOST}:{HDFS_PORT}") \
                .config("spark.hadoop.dfs.client.use.datanode.hostname", "true") \
                .config("spark.hadoop.dfs.datanode.use.datanode.hostname", "true")
        _spark = builder.getOrCreate()
    return _spark

def _load_books(spark: SparkSession, library: str, book: str, start_chapter: int, end_chapter: int) -> DataFrame:
    if library == "quran":
        dirs_to_load: list[str] = []
        for surah_num in range(start_chapter, end_chapter + 1):
            surah_name = _QURAN_SURAHS.get(surah_num)
            if surah_name is None:
                raise ValueError(f"Unknown surah number: {surah_num}")
            book_dir = book_path(library, surah_name)
            if not isdir(book_dir):
                raise FileNotFoundError(
                    f"Surah {surah_num} ({surah_name}) not found.\n"
                    f"Run: libquery download quran"
                )
            dirs_to_load.append(book_dir)
        return spark.read.parquet(*dirs_to_load)

    book_dir = book_path(library, book)
    if not isdir(book_dir):
        raise FileNotFoundError(
            f"No data for {library}/{book}.\n"
            f"Run: libquery download {library} {book}"
        )
    return spark.read.parquet(book_dir)

def execute(payload: dict[str, Any],ip :str) -> list[dict]: # Payload builds SQL query then returns rows to CLI
    print(f"\nFrom {ip}: Executing payload", json.dumps(payload, indent=2))
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
        {"chapter": r["chapter"], "verse": r["verse"], "text": r["text"].replace("\n", "\x1F"), "lang": r["lang"]}
        for r in rows if r["text"].strip()
    ]

def execute_sample(payload: dict[str, Any]) -> list[dict]:
    import os
    book = payload.get("book", "book1").lower()

    if book not in ("book1", "book2"):
        raise FileNotFoundError(
            f"Sample library only contains book1 and book2.\n"
            f"Try: libquery sample book1 1"
        )

    sample_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "data", "sample", book
    )
    sample_dir = os.path.normpath(sample_dir)

    if not os.path.isdir(sample_dir):
        raise FileNotFoundError(
            f"Sample data not found.\n"
            f"Ensure data/sample/ exists in the project root."
        )

    start_chapter = int(payload.get("start_chapter", 1))
    start_verse   = int(payload.get("start_verse",  NO_VERSE))
    end_chapter   = int(payload.get("end_chapter",  start_chapter))
    end_verse     = int(payload.get("end_verse",    NO_VERSE))
    lang          = payload.get("lang", None)

    if os.name == "nt":
        sample_url = "file:///" + sample_dir.replace("\\", "/")
    else:
        sample_url = "file://" + sample_dir

    spark = _get_spark()
    df = spark.read.parquet(sample_url)

    view_name = f"libq_{uuid.uuid4().hex}"
    try:
        df.createTempView(view_name)
        sql = build_query(
            "sample",
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
        {"chapter": r["chapter"], "verse": r["verse"],
         "text": r["text"].replace("\n", "\x1F"), "lang": r["lang"]}
        for r in rows if r["text"].strip()
    ]