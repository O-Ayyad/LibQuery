from __future__ import annotations
import re

NO_VERSE = -1  # mirrors the C constant
_SAFE_IDENTIFIER = re.compile(r'^[a-z0-9_\-]{1,64}$')
def _safe(value: str, field: str) -> str:
    if not _SAFE_IDENTIFIER.match(value):
        raise ValueError(
            f"Invalid {field} '{value}': only lowercase letters, digits, "
            "hyphens, and underscores are allowed."
        )
    return value

def build_query(
    library: str,
    start_chapter: int,
    start_verse: int = NO_VERSE,
    end_chapter: int | None = None,
    end_verse: int = NO_VERSE,
    lang: str | None = None,
) -> str:
    # default end_chapter = start_chapter

    library = _safe(library.lower(), "library")

    if end_chapter is None:
        end_chapter = start_chapter

    try:
        start_chapter = int(start_chapter)
        start_verse= int(start_verse)
        end_chapter= int(end_chapter)
        end_verse = int(end_verse)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid query parameter: {e}") from None

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
        start_cond = (
            f"(chapter = {start_chapter} AND verse >= {start_verse})"
            if start_verse != NO_VERSE
            else f"(chapter = {start_chapter})"
        )
        end_cond = (
            f"(chapter = {end_chapter} AND verse <= {end_verse})"
            if end_verse != NO_VERSE
            else f"(chapter = {end_chapter})"
        )
        
        if end_chapter - start_chapter > 1:
            mid_cond = f"(chapter > {start_chapter} AND chapter < {end_chapter})"
            conditions.append(f"{start_cond} OR {mid_cond} OR {end_cond}")
        else:
            conditions.append(f"{start_cond} OR {end_cond}")

    where_clause = " OR ".join(conditions)

    if lang is None:
        sql = (
            f"SELECT chapter, verse, text, lang FROM library "
            f"WHERE {where_clause} "
            f"ORDER BY chapter, verse, CASE WHEN lang = 'en' THEN 1 ELSE 0 END"
        )
    else:
        lang = _safe(lang.lower(), "lang")
        sql = (
            f"SELECT chapter, verse, text, lang FROM library "
            f"WHERE {where_clause} AND lang = '{lang}' "
            f"ORDER BY chapter, verse"
        )

    return sql

