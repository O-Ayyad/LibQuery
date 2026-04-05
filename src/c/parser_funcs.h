#ifndef PARSER_FUNCS_H
#define PARSER_FUNCS_H

#include <stdbool.h>
#include <stdio.h>
#include <stddef.h>

#define MAX_PATH 4096
#define MAX_LINE 4096
#define MAX_LENGTH_BEFORE_SPACE 96

#define NO_VERSE -1

typedef struct { //Start and end position of query
    int chapter;
    int verse;
} Position;

typedef struct { //Range to print text
    Position start;
    Position end;
} Range;

bool in_range(int chapter, int verse, Range range);
bool parse_position(const char *input, Position *out);
bool parse_range(const char *input, Range *out, bool is_single_chapter_lib);

#endif