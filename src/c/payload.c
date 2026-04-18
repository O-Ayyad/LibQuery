#ifndef _WIN32
    #define _POSIX_C_SOURCE 200809L
#endif

#include <stdio.h>
#include <string.h>
#include <stdbool.h>

#include "parser_funcs.h"
#include "net.h"
#include "payload.h"

#define LINE_WIDTH 200

void print_verse(int chapter, int verse, const char *text)
{
    char ref[16];
    snprintf(ref, sizeof(ref), "%d:%-4d ", chapter, verse);
    int ref_len = (int)strlen(ref);
    int text_width = LINE_WIDTH - ref_len;

    printf("%s", ref);

    int len = (int)strlen(text);
    int pos = 0;
    int first = 1;

    while (pos < len) {
        if (!first)
            printf("%*s", ref_len, "");

        int remaining = len - pos;
        if (remaining <= text_width) {
            printf("%s\n", text + pos);
            break;
        }

        int cut = text_width;
        while (cut > 0 && text[pos + cut] != ' ')
            cut--;
        if (cut == 0) cut = text_width;

        printf("%.*s\n", cut, text + pos);
        pos  += cut + 1;
        first = 0;
    }
    printf("\n");
}

void print_help(void)
{
    printf(
        "Usage:\n"
        "  libquery <library> <book> [ref]\n\n"
        "References:\n"
        "  4          Chapter 4\n"
        "  4:3        Chapter 4, verse 3\n"
        "  4-6        Chapters 4 through 6\n"
        "  4:3-6      4:3 through end of chapter 6\n"
        "  4-6:12     Start of chapter 4 through 6:12\n"
        "  4:3-6:12   4:3 through 6:12\n\n"
        "Examples:\n"
        "  libquery bible mark 4\n"
        "  libquery bible genesis 1:1-1:10\n"
        "  libquery quran 2:255\n\n"
        "Other commands:\n"
        "  libquery download bible mark                 Downloads a book\n"
        "  libquery download bible                      Downloads entire library\n"
        "  libquery host                                Hosts the server\n"
        "  libquery ping                                Check server connection\n"
        "  libquery restart                             Restarts the server\n"
        "  libquery alias <library>/<book> <alias>      Allows calling of books with an alias\n"
        "  libquery target <IP>                         Changes target IP. Use libquery target help for more information.\n"
        "  libquery ls <optional: library>              Lists all available libraries or books within a library\n"
    );
}

int query(const char *library, const char *book, bool use_range, Range range)
{
    if (!server_online()) {
        fprintf(stderr, "[Client] Error: Server is not online\n");
        return 1;
    }

    char payload[1024];
    if (!use_range) {
        snprintf(payload, sizeof(payload),
            "{\"cmd\":\"query\","
            "\"library\":\"%s\","
            "\"book\":\"%s\","
            "\"start_chapter\":1,"
            "\"start_verse\":-1,"
            "\"end_chapter\":999,"
            "\"end_verse\":-1}",
            library, book);
    } else {
        snprintf(payload, sizeof(payload),
            "{\"cmd\":\"query\","
            "\"library\":\"%s\","
            "\"book\":\"%s\","
            "\"start_chapter\":%d,"
            "\"start_verse\":%d,"
            "\"end_chapter\":%d,"
            "\"end_verse\":%d}",
            library, book,
            range.start.chapter,
            range.start.verse,
            range.end.chapter,
            range.end.verse);
    }

    return send_and_print(payload);
}

int download(const char *library, const char *book)
{
    if (!server_online()) {
        fprintf(stderr, "Server is not online\n");
        return 1;
    }

    char payload[512];
    if (book)
        snprintf(payload, sizeof(payload),
            "{\"cmd\":\"download\",\"library\":\"%s\",\"book\":\"%s\"}",
            library, book);
    else
        snprintf(payload, sizeof(payload),
            "{\"cmd\":\"download\",\"library\":\"%s\"}",
            library);

    return send_and_print(payload);
}

int download_all(void)
{
    if (!server_online()) {
        fprintf(stderr, "Server is not online\n");
        return 1;
    }

    printf("\n             WARNING! This will download every single book from every library.\n"
           "               This may take minutes to download and will prevent the server from executing anything.\n"
           "               Are you sure you want to download everything [Y/N]\n\n");
    fflush(stdout);

    char input[16];
    if (!fgets(input, sizeof(input), stdin))
        return 1;
    if (input[0] != 'y' && input[0] != 'Y') {
        printf("Cancelled.\n");
        return 0;
    }

    char payload[512];
    snprintf(payload, sizeof(payload), "{\"cmd\":\"download\",\"library\":\"all\"}");
    return send_and_print(payload);
}