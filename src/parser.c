#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <sys/stat.h>

#include "parser_funcs.h"


bool is_directory(const char *path)
{
    struct stat info;
    return stat(path, &info) == 0 && S_ISDIR(info.st_mode);
}

// Check if a chapter/verse falls inside the requested range
bool in_range(int chapter, int verse, Range range)
{
    // if no start verse was given, start from verse 1 (3-4:12)
    int start_verse = (range.start.verse == NO_VERSE) ? 1 : range.start.verse;

    //are we at or past the start?
    bool on_later_chapter = chapter > range.start.chapter;
    bool on_start_chapter = (chapter == range.start.chapter) && (verse >= start_verse);
    bool after_start      = on_later_chapter || on_start_chapter;

    /* are we at or before the end? */
    bool end_is_whole_chapter = (range.end.verse == NO_VERSE);
    bool before_end_chapter   = chapter < range.end.chapter;
    bool on_end_chapter       = (chapter == range.end.chapter) && (verse <= range.end.verse);
    bool before_end           = end_is_whole_chapter ? chapter <= range.end.chapter
                                                     : before_end_chapter || on_end_chapter;

    return after_start && before_end;
}

//Parse 3 or 3:16 into a postition
bool parse_position(const char *input, Position *out)
{
    // check if there is a colon 
    const char *colon = strchr(input, ':');

    if (colon) {

        //split into chapter and verse
        char chapter_str[16];
        char verse_str[16];

        int chapter_len = (int)(colon - input);
        if (chapter_len <= 0 || chapter_len >= 16) return false;

        memcpy(chapter_str, input, (size_t)chapter_len);
        chapter_str[chapter_len] = '\0';

        memcpy(verse_str, colon + 1, 15);
        verse_str[15] = '\0';

        //are both are numbers
        for (int i = 0; chapter_str[i]; i++) {
            if (!isdigit((unsigned char)chapter_str[i])) return false;
        }
        for (int i = 0; verse_str[i]; i++) {
            if (!isdigit((unsigned char)verse_str[i])) return false;
        }

        out->chapter = atoi(chapter_str);
        out->verse = atoi(verse_str);
    } else {
        // no colon so its just a chapter number 
        for (int i = 0; input[i]; i++) {
            if (!isdigit((unsigned char)input[i])) return false;
        }
        out->chapter = atoi(input);
        out->verse   = NO_VERSE;
    }

    return out->chapter > 0;
}

// Parse a full reference like "1", "2:15", "1-3", "2:15-3:19"
bool parse_range(const char *input, Range *out)
{
    // Find the dash
    const char *dash = strchr(input, '-');

    if (dash) {
        // split into start and end strings around the dash
        char start_str[32];
        char end_str[32];

        int start_len = (int)(dash - input);
        int end_len   = (int)strlen(dash + 1);

        if (start_len <= 0 || start_len >= 32) return false;
        if (end_len   <= 0 || end_len   >= 32) return false;

        memcpy(start_str, input,    (size_t)start_len);
        start_str[start_len] = '\0';

        memcpy(end_str, dash + 1, (size_t)end_len);
        end_str[end_len] = '\0';

        if (!parse_position(start_str, &out->start) ||
            !parse_position(end_str,   &out->end)) {
            return false;
        }

        // validate order
        if (out->end.chapter < out->start.chapter ||
           (out->end.chapter == out->start.chapter &&
            out->end.verse != NO_VERSE &&
            out->start.verse != NO_VERSE &&
            out->end.verse < out->start.verse)) {
            return false;
        }

        return true;
        
    } else {
        // No dash so either an entire chapter or a single verse
        if (!parse_position(input, &out->start)) return false;
        out->end = out->start;
        return true;
    }
}