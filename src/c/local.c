#ifndef _WIN32
    #define _POSIX_C_SOURCE 200809L
#endif

#include <stdio.h>
#include <string.h>
#include <unistd.h>

#ifdef _WIN32
    #include <windows.h>
#endif

#include "utils.h"
#include "local.h"

FILE *run_python(char *path, char *args)
{
    char exe_path[4096];
    char command[512];

#ifdef _WIN32
    GetModuleFileNameA(NULL, exe_path, sizeof(exe_path));
    char *slash = strrchr(exe_path, '\\');
    if (slash) *slash = '\0';
    snprintf(command, sizeof(command),
             "py \"%s\\%s\" %s", exe_path, path, args ? args : "");
#else
    ssize_t count = readlink("/proc/self/exe", exe_path, sizeof(exe_path) - 1);
    if (count != -1) exe_path[count] = '\0';
    char *slash = strrchr(exe_path, '/');
    if (slash) *slash = '\0';
    snprintf(command, sizeof(command),
             "python3 \"%s/%s\" %s", exe_path, path, args ? args : "");
#endif

    return popen(command, "r");
}

int is_safe_path(const char *s)
{
    for (const char *p = s; *p; p++) {
        if (*p == '&' || *p == '|' || *p == '^' || *p == '%')
            return 0;
    }
    return 1;
}

char *resolve_alias(const char *token)
{
    char subcmd[256];
    snprintf(subcmd, sizeof(subcmd), "resolve %s", token);

#ifdef _WIN32
    FILE *fp = run_python("src\\python\\local\\alias_handler.py", subcmd);
#else
    FILE *fp = run_python("src/python/local/alias_handler.py", subcmd);
#endif

    static char resolved[256];
    strncpy(resolved, token, sizeof(resolved) - 1);
    resolved[sizeof(resolved) - 1] = '\0';

    if (!fp) return resolved;

    if (fgets(resolved, sizeof(resolved), fp) != NULL)
        resolved[strcspn(resolved, "\r\n")] = '\0';

    pclose(fp);
    return resolved;
}

char *alias(char **args, int argc)
{
    char subcmd[1024] = "";
    for (int i = 0; i < argc; i++) {
        strncat(subcmd, args[i], sizeof(subcmd) - strlen(subcmd) - 1);
        if (i < argc - 1)
            strncat(subcmd, " ", sizeof(subcmd) - strlen(subcmd) - 1);
    }

#ifdef _WIN32
    FILE *fp = run_python("src\\python\\local\\alias_handler.py", subcmd);
#else
    FILE *fp = run_python("src/python/local/alias_handler.py", subcmd);
#endif

    if (!fp) return NULL;

    static char result[2048];
    result[0] = '\0';
    char line[256];
    while (fgets(line, sizeof(line), fp) != NULL)
        strncat(result, line, sizeof(result) - strlen(result) - 1);
    pclose(fp);

    size_t len = strlen(result);
    if (len > 0 && result[len - 1] == '\n')
        result[len - 1] = '\0';

    return result;
}

char *target_ip(char *payload)
{
    char cmd[64] = {0};
    strncpy(cmd, payload, sizeof(cmd) - 1);

#ifdef _WIN32
    FILE *fp = run_python("src\\python\\local\\network_handler.py", cmd);
#else
    FILE *fp = run_python("src/python/local/network_handler.py", cmd);
#endif

    if (!fp) return NULL;

    static char result[2048];
    if (fgets(result, sizeof(result), fp) == NULL) {
        pclose(fp);
        return NULL;
    }
    pclose(fp);

    result[strcspn(result, "\n")] = '\0';
    return result;
}