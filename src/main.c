/*
 *   libquery <library> <book>             Print entire book
 *   libquery <library> <book> <N>         Print chapter N
 *   libquery <library> <book> <N:V>       Print single verse
 *   libquery <library> <book> <N-M>       Print chapter N through end of chapter M
 *   libquery <library> <book> <N:V-M>     Print N:V through end of chapter M
 *   libquery <library> <book> <N-M:V>     Print start of chapter N through M:V
 *   libquery <library> <book> <N:V-M:W>   Print N:V through M:W
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <ctype.h>
#include <sys/stat.h>
#include <unistd.h>
#include <Python.h>

#include "parser_funcs.h"

#ifdef _WIN32
#include <windows.h>
#else
#include <strings.h>
#endif

static int strcmpci(const char *a, const char *b)
{
#ifdef _WIN32
    return _stricmp(a, b);
#else
    return strcasecmp(a, b);
#endif
}

static bool find_library(const char *name, char *result, size_t result_size)
{
    char debug_cwd[MAX_PATH];
    getcwd(debug_cwd, sizeof(debug_cwd));
    fprintf(stderr, "DEBUG cwd: %s\n", debug_cwd);

    char searches[4][MAX_PATH * 2];
    int count = 0;

    #ifdef _WIN32
    char exe_dir[MAX_PATH];
    if (GetModuleFileNameA(NULL, exe_dir, sizeof(exe_dir))) {
        char *last_slash = strrchr(exe_dir, '\\');
        if (last_slash) *last_slash = '\0';
        snprintf(searches[count++], MAX_PATH * 2, "%s\\%s", exe_dir, name);
        snprintf(searches[count++], MAX_PATH * 2, "%s\\data\\%s", exe_dir, name);
    }
    #endif

    //find working dir
    char cwd[MAX_PATH];
    if (getcwd(cwd, sizeof(cwd))) {
        #ifdef _WIN32
        snprintf(searches[count++], MAX_PATH * 2, "%s\\%s",      cwd, name);
        snprintf(searches[count++], MAX_PATH * 2, "%s\\data\\%s", cwd, name);
        #else
        snprintf(searches[count++], MAX_PATH * 2, "%s/%s",      cwd, name);
        snprintf(searches[count++], MAX_PATH * 2, "%s/data/%s", cwd, name);
        #endif
    }

    //try each candidate in order
    for (int i = 0; i < count; i++) {
        if (is_directory(searches[i])) {
            memcpy(result, searches[i], result_size - 1);
            result[result_size - 1] = '\0';
            return true;
        }
    }

    // last resort treat name as a direct path
    if (is_directory(name)) {
        strncpy(result, name, result_size - 1);
        result[result_size - 1] = '\0';
        return true;
    }

    return false;
}
bool find_book(const char *library_path, const char *book_name, char *result, size_t result_size)
{
    char lowercase[256];
    char titlecase[256];
    char candidate[MAX_PATH * 2];

    //lowercase version of the book name
    strncpy(lowercase, book_name, sizeof(lowercase) - 1);
    lowercase[sizeof(lowercase) - 1] = '\0';
    for (int i = 0; lowercase[i]; i++) {
        lowercase[i] = (char)tolower((unsigned char)lowercase[i]);
    }

    // build a title case genesis to Genesis
    strncpy(titlecase, lowercase, sizeof(titlecase) - 1);
    titlecase[sizeof(titlecase) - 1] = '\0';
    if (titlecase[0]) {
        titlecase[0] = (char)toupper((unsigned char)titlecase[0]);
    }

    //try each name variant
    const char *name_variants[] = { book_name, lowercase, titlecase };
    for (int i = 0; i < 3; i++) {
        snprintf(candidate, sizeof(candidate), "%s/%s.csv", library_path, name_variants[i]);
        struct stat info;
        if (stat(candidate, &info) == 0) {
            memcpy(result, candidate, result_size - 1);
            result[result_size - 1] = '\0';
            return true;
        }
    }

    return false;
}

const char *read_csv_field(const char *cursor, char *out, int max)
{
    int i = 0;
    if (*cursor == '"') {
        cursor++;
        while (*cursor && i < max - 1) {
            if (*cursor == '"') {
                cursor++;
                // double quote is literal quote
                if (*cursor == '"') {
                    out[i++] = '"';
                    cursor++;
                } else {
                    break;
                }
            } else {
                out[i++] = *cursor++;
            }
        }
        if (*cursor == ',') cursor++;
    } else {
        while (*cursor && *cursor != ',' && i < max - 1) {
            out[i++] = *cursor++;
        }
        if (*cursor == ',') cursor++;
    }

    out[i] = '\0';
    return cursor;
}

void query(FILE *csv, bool use_range, Range range)
{
    char line[MAX_LINE];
    bool first_row = true;

    while (fgets(line, sizeof(line), csv)) {
        int len = (int)strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
            line[--len] = '\0';
        }
        if (len == 0) continue;

        char chapter_field[32];
        char verse_field[32];

        char text_field[MAX_LINE];
        const char *cursor = line;
        cursor = read_csv_field(cursor, chapter_field, (int)sizeof(chapter_field));
        cursor = read_csv_field(cursor, verse_field, (int)sizeof(verse_field));
                 read_csv_field(cursor, text_field, (int)sizeof(text_field));
        // skip header
        if (first_row) {
            first_row = false;
            if (!isdigit((unsigned char)chapter_field[0])) continue;
        }
        //add newline when verse is too long
        int text_length = strlen(text_field);
        if(text_length > MAX_LENGTH_BEFORE_SPACE){
            for(int i = 0; i < (text_length / MAX_LENGTH_BEFORE_SPACE ); i++){
                char* curr = &text_field[(i+1)*MAX_LENGTH_BEFORE_SPACE];

                for (; *curr != '\0' && *curr != ' '; curr++);

                if (*curr == ' ') {
                    memmove(curr + 7, curr + 1, strlen(curr + 1) + 1);
                    *curr       = '\n';
                    *(curr + 1) = ' ';
                    *(curr + 2) = ' ';
                    *(curr + 3) = ' ';
                    *(curr + 4) = ' ';
                    *(curr + 5) = ' ';
                    *(curr + 6) = ' ';
                    text_length += 6;
                }
            }
        }
        int chapter = atoi(chapter_field);
        int verse   = atoi(verse_field);
        if (chapter <= 0 || verse <= 0) continue;

        if (!use_range || in_range(chapter, verse, range)) {
            printf("%d:%-3d %s\n\n", chapter, verse, text_field);
        }
    }
}
void print_help(){
    fprintf(stderr,
        "Usage:\n"
        "  libquery <library> <book> [ref]\n\n"
        "Examples:\n"
        "  libquery bible Genesis 1\n"
        "  libquery bible Exodus 2-3\n"
        "  libquery bible John 3:16\n"
        "  libquery bible Romans 1:19-1:21\n"
    );
}
enum supported_libraries parse_library_name(char* library){
    if(strcmpci(library, "bible") == 0){
        return LIBRARY_BIBLE;
    }
    if(strcmpci(library, "quran") == 0){
        return LIBRARY_QURAN;
    }
    if(strcmpci(library, "shakespeare") == 0){
        return LIBRARY_SHAKESPEARE;
    }
    if(strcmpci(library, "poe") == 0){
        return LIBRARY_POE;
    }
    return NO_LIBRARY;
}
void handle_install(char* library, char* book){
    enum supported_libraries selected_library = parse_library_name(library);

    if(selected_library == NO_LIBRARY){
        fprintf(stderr,
            "Library %s is not supported or does not exist.", library
        );
        return 0;
    }

    switch(selected_library){
        case(LIBRARY_BIBLE):{

        }
        case(LIBRARY_QURAN):{
            
        }
        case(LIBRARY_SHAKESPEARE):{
            
        }
        case(LIBRARY_POE):{
            
        }
    }
}
int main(int argc, char *argv[])
{   
    if (argc > 4) { //To many args
        fprintf(stderr, "Too many arguments.\n");
        return 1;
    }
    if(argc <= 1 || argv[2] == "help"){ //Help
        print_help();
        return 1;
    }
    if(argv[2] == "install"){ //Install book
        if(argc == 3){ //Install entire library
            handle_install(argv[3], NULL);
        }else{ //Install only the book
            handle_install(argv[3], argv[4]);
        }
    }

    //TODO: check if it is quran since "libquery quran 12:12" is valid
    if (argc < 3) {

        return 1;
    }

    char library_path[MAX_PATH];
    char book_path[MAX_PATH];

    //find the library folder
    if (!find_library(argv[1], library_path, sizeof(library_path))) {
        fprintf(stderr, "Error: library directory '%s' not found.\n", argv[1]);
        return 1;
    }

    //find the book csv inside it
    if (!find_book(library_path, argv[2], book_path, sizeof(book_path))) {
        fprintf(stderr, "Error: book '%s' not found in '%s'.\n", argv[2], library_path);
        return 1;
    }

    //open the file
    FILE *file = fopen(book_path, "r");
    if (!file) {
        perror("Error opening CSV");
        return 1;
    }

    // parse the optional reference argument
    bool use_range = false;
    Range range;
    memset(&range, 0, sizeof(range));

    if (argc >= 4) {
        if (!parse_range(argv[3], &range)) {
            fprintf(stderr, "Error: cannot parse reference '%s'.\n", argv[3]);
            fclose(file);
            return 1;
        }
        use_range = true;
    }

    query(file, use_range, range);
    fclose(file);
    return 0;
}