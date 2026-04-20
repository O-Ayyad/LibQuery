#ifndef _WIN32
    #define _POSIX_C_SOURCE 200809L
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <sys/stat.h>
#include <unistd.h>

#ifdef _WIN32
    #include <windows.h>
#endif

#include "utils.h"

#define TOKEN_LEN 64
#define TOKEN_SUBPATH  "data/serverdata/admin.token"

static char token_path[4096];

void get_project_root(char *out, size_t size)
{
#ifdef _WIN32
    GetModuleFileNameA(NULL, out, (DWORD)size);
    char *last = strrchr(out, '\\');
    if (last) *last = '\0';
#else
    ssize_t n = readlink("/proc/self/exe", out, size - 1);
    if (n == -1) { out[0] = '\0'; return; }
    out[n] = '\0';
    char *last = strrchr(out, '/');
    if (last) *last = '\0';
#endif
}

void resolve_token_path(void)
{
    char path[512] = "";
    get_project_root(path, sizeof(path));

#ifdef _WIN32
    snprintf(token_path, sizeof(token_path),
             "%s\\data\\serverdata\\admin.token", path);
#else
    snprintf(token_path, sizeof(token_path),
             "%s/data/serverdata/admin.token", path);
#endif
}

char *load_admin_token(void)
{
    FILE *f = fopen(token_path, "r");
    if (!f) {
        fprintf(stderr, "[Client] Error: could not open token file: %s\n", token_path);
        return NULL;
    }

    char *token = malloc(TOKEN_LEN + 1);
    if (!token) {
        fclose(f);
        return NULL;
    }

    if (!fgets(token, TOKEN_LEN + 1, f)) {
        fprintf(stderr, "[Client] Error: could not read token\n");
        fclose(f);
        free(token);
        return NULL;
    }
    fclose(f);

    token[strcspn(token, "\r\n")] = '\0';

    if (strlen(token) != TOKEN_LEN) {
        fprintf(stderr, "[Client] Error: token malformed (len=%zu)\n", strlen(token));
        free(token);
        return NULL;
    }

    return token;
}
int is_valid_name(const char *s)
{
    if (s == NULL) return 1;
    if (*s == '\0') return 0;
    for (const char *p = s; *p; p++) {
        if (!isalnum((unsigned char)*p) && *p != '_' && *p != '-')
            return 0;
    }
    return 1;
}

int is_valid_keyword(const char *s)
{
    if (s == NULL || *s == '\0') return 0;
    for (const char *p = s; *p; p++) {
        if (*p == '"' || *p == '\\' || *p == '\n' || *p == '\r')
            return 0;
    }
    return 1;
}

int hadoop_available(char *project_root)
{
#ifdef _WIN32
    char path[512];
    struct stat st;

    snprintf(path, sizeof(path), "%s\\hadoop\\bin\\winutils.exe", project_root);
    if (stat(path, &st) == 0) return 1;

    snprintf(path, sizeof(path), "C:\\hadoop\\bin\\winutils.exe");
    return stat(path, &st) == 0;
#else
    (void)project_root;
    return 1;
#endif
}