#ifndef _WIN32
    #define _POSIX_C_SOURCE 200809L
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifdef _WIN32
    #include <windows.h>
#else
    #include <sys/types.h>
    #include <sys/wait.h>
#endif

#include "utils.h"
#include "net.h"
#include "server_handler.h"
#include "local.h"

typedef struct {
    const char *name;
    Server_Commands  cmd;
} CommandEntry;

static const CommandEntry COMMANDS[] = {
    { "host", CMD_HOST},
    { "close",  CMD_CLOSE},
    { "restart", CMD_RESTART},
};

Server_Commands parse_command(char *cmd)
{
    for (int i = 0; i < (int)(sizeof(COMMANDS) / sizeof(COMMANDS[0])); i++) {
        if (strcasecmp(cmd, COMMANDS[i].name) == 0)
            return COMMANDS[i].cmd;
    }
    return UNKNOWN;
}

int is_server_command(char *cmd)
{
    return (strcasecmp(cmd, "host") == 0 ||
            strcasecmp(cmd, "close") == 0 ||
            strcasecmp(cmd, "restart") == 0);
}

int host_server(void)
{
    if (server_online()) {
        fprintf(stderr, "[Client] Error: Server is already running.\n");
        return 1;
    }
    printf("Starting server.\n");

    char exe_path[4096];
    char command[1024];

#ifdef _WIN32
    GetModuleFileNameA(NULL, exe_path, sizeof(exe_path));
#else
    ssize_t count = readlink("/proc/self/exe", exe_path, sizeof(exe_path) - 1);
    if (count != -1) exe_path[count] = '\0';
#endif

    char *slash = strrchr(exe_path,
#ifdef _WIN32
        '\\'
#else
        '/'
#endif
    );
    if (slash) *slash = '\0';

    if (!is_safe_path(exe_path)) {
        fprintf(stderr, "[Client] Error: unsafe path detected.\n");
        return 1;
    }

#ifdef _WIN32
    snprintf(command, sizeof(command),
        "start \"LibQuery Server\" cmd /c "
        "\"cd /d %s\\src\\python && python -m networking.server\"",
        exe_path);

    int result = system(command);
    if (result != 0) {
        fprintf(stderr, "[Client] Error: could not open terminal to host server.\n");
        return -2;
    }
#else
    char python_dir[4096];
    snprintf(python_dir, sizeof(python_dir), "%s/src/python", exe_path);

    pid_t pid = fork();
    if (pid == 0) {
        chdir(python_dir);
        execlp("gnome-terminal", "gnome-terminal",
               "--", "bash", "-c",
               "python3 -m networking.server; exec bash",
               NULL);
        execlp("konsole", "konsole",
               "-e", "bash", "-c",
               "python3 -m networking.server; exec bash",
               NULL);
        execlp("xfce4-terminal", "xfce4-terminal",
               "-e", "bash", "-c",
               "python3 -m networking.server; exec bash",
               NULL);
        execlp("xterm", "xterm",
               "-e", "python3 -m networking.server",
               NULL);
        perror("[Client] Error: no terminal emulator found");
        _exit(1);
    } else if (pid < 0) {
        fprintf(stderr, "[Client] Error: fork failed.\n");
        return -2;
    }
    /* parent falls through to the ping loop below */
    (void)command;
#endif

    fflush(stdout);
    printf("Waiting for server to respond...\n\n");
    const int timeout_ms  = 30000;
    const int interval_ms = 500;
    int waited_ms = 0;

    while (waited_ms < timeout_ms) {
        if (ping_local() == 0) {
            fprintf(stdout, "Server hosted locally on port 9237\n");
            return 0;
        }

    #ifdef _WIN32
        Sleep(interval_ms);
    #else
        usleep(interval_ms * 1000);
    #endif

        waited_ms += interval_ms;

        if (waited_ms % 5000 == 0){
            printf("Still waiting... (%ds)\n", waited_ms / 1000);
        }
    }
    fprintf(stderr,
            "[Client] Error: server did not respond within %d seconds.\n"
            "       It may have crashed on startup.\n"
            "       Check the server terminal window for error output.\n",
            timeout_ms / 1000);
    return 1;
}

int close_server(void)
{
    if (!server_online())
        return 1;

    char *token = load_admin_token();
    if (!token) return 1;

    char buf[512];
    snprintf(buf, sizeof(buf),
             "{\"cmd\":\"close\",\"token\":\"%s\"}", token);

    free(token);
    return send_and_print_local(buf);
}

int restart_server(void)
{
    int a = close_server();
#ifdef _WIN32
    Sleep(2000);
#else
    sleep(2);
#endif
    int b = host_server();
    return a || b;
}