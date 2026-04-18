#ifndef PAYLOAD_H
#define PAYLOAD_H

#include <stdbool.h>

void print_verse(int chapter, int verse, const char *text);
void print_help(void);
int query(const char *library, const char *book, bool use_range, Range range);
int download(const char *library, const char *book);
int download_all(void);

#endif
