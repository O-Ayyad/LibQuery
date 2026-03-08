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
void handle_download(char* library, char* book){
    enum supported_libraries selected_library = parse_library_name(library);

    if(selected_library == NO_LIBRARY){
        fprintf(stderr,
            "Library %s is not supported or does not exist.", library
        );
        return;
    }

    if(!book){
        book = "download_entire_library";
    }
    
    char exe_path[MAX_PATH];
    char command[512];

    GetModuleFileNameA(NULL, exe_path, sizeof(exe_path));
    char* slash = strrchr(exe_path, '\\');
    if (slash) {
        *slash = '\0';
    }

    #ifdef _WIN32
    snprintf(command, sizeof(command), "cmd /c py \"%s\\src\\python\\download_libs.py\" %s %s \"%s\"",  
    exe_path, 
    library ? library : "", 
    book ? book : "",
    exe_path);
    #else
    snprintf(command, sizeof(command), "python3 \"%s/src/python/download_libs.py\" %s %s \"%s\"", 
    exe_path, 
    library ? library : "", 
    book ? book : "",
    exe_path);
    #endif
    FILE *python = popen(command, "r");
    if (!python) {
        fprintf(stderr, "Error: could not run download script.\n");
        return;
    }

    char line[256];
    while (fgets(line, sizeof(line), python)) {
        printf("%s", line);
    }

    pclose(python);
    
}

typedef struct{
    char* library;
    char* book;
    char* ref;
    int* flags; // bool arry for each possible flags
    int download;
} arguments_and_flags;

arguments_and_flags format_args(int argc, char **argv)
{
    arguments_and_flags af = {0};
    af.download = (strcmpci(argv[1],"download") == 0);

    int no_lib = (argc >= 2 && strcmpci(argv[1], "quran") == 0);
        if (af.download) {
        /* libquery download bible genesis */
            af.library = (argc >= 3) ? argv[2] : NULL;
            af.book = (argc >= 4) ? argv[3] : NULL;
            af.ref = NULL;
        return af;
    }
    if (no_lib) {
        af.library = "quran";
        af.book = "quran";
        af.ref = (argc >= 3) ? argv[2] : NULL;
    } else {
        af.library = (argc >= 2) ? argv[1] : NULL;
        af.book = (argc >= 3) ? argv[2] : NULL;
        af.ref = (argc >= 4) ? argv[3] : NULL;
    }

    af.flags = NULL;
    return af;
}
void print_help(){
    fprintf(stdout,
        "Usage:\n"
        "  libquery <library> <book> [ref] [flags]\n\n"
        "  or for books without a library:\n\n"
        "  libquery <book> [ref] [flags]\n\n"
        "Examples:\n"
        "  libquery bible Genesis 1          (Prints Genesis 1)\n"
        "  libquery bible Exodus 2-4         (Prints Exodus 2,3, and 4)\n"
        "  libquery bible john 3:16          (Prints John 3:16)\n"
        "  libquery quran 2:1-2:10           (Prints the first 10 verses of the second chapter)"   
    );
}
void print_welcome(){
        fprintf(stdout,
        "Temporary welcome message and simple commands"
    );
}
int main(int argc, char *argv[])
{   
    if(argc == 1){
        print_welcome();
        return 0;
    }
    if(argc == 2 && ((strcmpci(argv[1],"help") == 0) || strcmpci(argv[1],"h") == 0)){
        print_help();
        return 0;
    }

    arguments_and_flags all_args = format_args(argc, argv);

    if (all_args.download) {
        handle_download(all_args.library, all_args.book);
        return 0;
    }

    char* library = all_args.library;
    char* book = all_args.book;
    char* ref = all_args.ref;

    if (!library) {
        fprintf(stderr, "Error: no library specified.\n");
        return 1;
    }
    if (!book) {
        fprintf(stderr, "Error: no book specified.\n");
        return 1;
    }

    char library_path[MAX_PATH];
    char book_path[MAX_PATH];

    //find the library folder
    if (!find_library(library, library_path, sizeof(library_path))) {
        fprintf(stderr, "Error: library directory '%s' not found.\n", library);
        return 1;
    }

    //find the book csv inside it
    if (!find_book(library_path, book, book_path, sizeof(book_path))) {
        fprintf(stderr, "Error: book '%s' not found in '%s'.\n", book, library_path);
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
        if (!parse_range(ref, &range)) {
            fprintf(stderr, "Error: cannot parse reference '%s'.\n", ref);
            fclose(file);
            return 1;
        }
        use_range = true;
    }

    query(file, use_range, range);
    fclose(file);
    return 0;
}