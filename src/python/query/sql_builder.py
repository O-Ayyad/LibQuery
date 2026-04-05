from __future__ import annotations

NO_VERSE = -1  # mirrors the C constant
def build_query(
    library:     str,
    book:        str,
    *,
    start_chapter: int,
    start_verse:   int = NO_VERSE,
    end_chapter:   int | None = None,
    end_verse:     int = NO_VERSE,
    lang:          str = "en",
) -> str:
    """
    Return a SparkSQL SELECT that reads from the 'library' temp view and
    returns matching (chapter, verse, text) rows ordered correctly.

    The view has columns: library, book, chapter, verse, text, lang
    """
    if end_chapter is None:
        end_chapter = start_chapter

    conditions = [
        f"library = '{library.lower()}'",
        f"lang = '{lang}'",
    ]

    if not (library == "quran" and book == "quran"):
        conditions.append(f"book = '{book.lower()}'")

    # Effective start verse
    sv = 1 if start_verse == NO_VERSE else start_verse

    if start_chapter == end_chapter:
        # Same chapter
        conditions.append(f"chapter = {start_chapter}")
        if start_verse != NO_VERSE and end_verse != NO_VERSE:
            conditions.append(f"verse BETWEEN {sv} AND {end_verse}")
        elif start_verse != NO_VERSE:
            conditions.append(f"verse >= {sv}")
        elif end_verse != NO_VERSE:
            conditions.append(f"verse <= {end_verse}")
        # else whole chapter - no verse filter
    else:
        after_start = (
            f"(chapter > {start_chapter} OR "
            f"(chapter = {start_chapter} AND verse >= {sv}))"
        )
        if end_verse == NO_VERSE:
            before_end = f"chapter <= {end_chapter}"
        else:
            before_end = (
                f"(chapter < {end_chapter} OR "
                f"(chapter = {end_chapter} AND verse <= {end_verse}))"
            )
        conditions.append(after_start)
        conditions.append(before_end)

    where = "\n  AND ".join(conditions)
    return (
        f"SELECT chapter, verse, text\n"
        f"FROM   library\n"
        f"WHERE  {where}\n"
        f"ORDER BY chapter, verse"
    )


def build_single_verse_query(library: str, book: str, chapter: int, verse: int, lang: str = "en") -> str:
    return build_query(library, book,
                       start_chapter=chapter, start_verse=verse,
                       end_chapter=chapter,   end_verse=verse,
                       lang=lang)


def build_chapter_query(library: str, book: str, chapter: int, lang: str = "en") -> str:
    return build_query(library, book,
                       start_chapter=chapter,
                       end_chapter=chapter,
                       lang=lang)
