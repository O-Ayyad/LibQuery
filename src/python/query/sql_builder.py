from __future__ import annotations

NO_VERSE = -1  # mirrors the C constant

def build_query(
    library: str,
    book: str,
    *,
    start_chapter: int,
    start_verse: int = NO_VERSE,
    end_chapter: int | None = None,
    end_verse: int = NO_VERSE,
    lang: str = "en",
) -> str:
    # default end_chapter = start_chapter
    if end_chapter is None:
        end_chapter = start_chapter

    conditions = []

    if start_chapter == end_chapter:
        if start_verse != NO_VERSE and end_verse != NO_VERSE:
            conditions.append(f"(chapter = {start_chapter} AND verse BETWEEN {start_verse} AND {end_verse})")
        elif start_verse != NO_VERSE:
            conditions.append(f"(chapter = {start_chapter} AND verse >= {start_verse})")
        elif end_verse != NO_VERSE:
            conditions.append(f"(chapter = {start_chapter} AND verse <= {end_verse})")
        else:
            conditions.append(f"(chapter = {start_chapter})")
    else:

        start_cond = f"(chapter = {start_chapter} AND verse >= {start_verse})" if start_verse != NO_VERSE else f"(chapter = {start_chapter})"
        end_cond = f"(chapter = {end_chapter} AND verse <= {end_verse})" if end_verse != NO_VERSE else f"(chapter = {end_chapter})"
        
        if end_chapter - start_chapter > 1:
            mid_cond = f"(chapter > {start_chapter} AND chapter < {end_chapter})"
            conditions.append(f"{start_cond} OR {mid_cond} OR {end_cond}")
        else:
            conditions.append(f"{start_cond} OR {end_cond}")

    where_clause = " OR ".join(conditions)

    if library.lower() == "quran":
        # Return both Arabic and English
        sql = (
            f"SELECT chapter, verse, text, lang FROM library "
            f"WHERE {where_clause} "
            f"ORDER BY chapter, verse, CASE WHEN lang = 'ar' THEN 0 ELSE 1 END"
        )
    else:
        sql = (
            f"SELECT chapter, verse, text, lang FROM library "
            f"WHERE {where_clause} AND lang = '{lang}' "
            f"ORDER BY chapter, verse"
        )

    return sql

