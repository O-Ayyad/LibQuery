#ifndef _WIN32
    #define _POSIX_C_SOURCE 200809L
#endif
 
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
 
#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #define CLOSE_SOCKET(s) closesocket(s)
    typedef SOCKET sock_t;
#else
    #include <sys/socket.h>
    #include <arpa/inet.h>
    #define CLOSE_SOCKET(s) close(s)
    typedef int sock_t;
#endif
 
#include "utils.h"
#include "net.h"
 
#define SERVER_PORT  9237
#define LINE_WIDTH   200
 
/* Flags for send_and_print_impl */
#define SEND_FLAG_LOCAL  1
#define SEND_FLAG_QUIET  2
#define SEND_FLAG_BOTH   3
 
int net_init(void)
{
#ifdef _WIN32
    WSADATA wsa;
    return WSAStartup(MAKEWORD(2, 2), &wsa);
#else
    return 0;
#endif
}
 
void net_cleanup(void)
{
#ifdef _WIN32
    WSACleanup();
#endif
}
 
char *get_ip(void)
{
    static char result[128];
    char config_path[512];
    char project_root[512];
    get_project_root(project_root, sizeof(project_root));
 
    snprintf(config_path, sizeof(config_path),
             "%s/data/userdata/networking_config.json", project_root);
 
    FILE *f = fopen(config_path, "r");
    if (!f) return "127.0.0.1";
 
    char buf[1024];
    size_t n = fread(buf, 1, sizeof(buf) - 1, f);
    buf[n] = '\0';
    fclose(f);
 
    char *key = strstr(buf, "\"target_ip\"");
    if (!key) return "127.0.0.1";
 
    char *colon = strchr(key, ':');
    if (!colon) return "127.0.0.1";
 
    char *quote = strchr(colon, '"');
    if (!quote) return "127.0.0.1";
 
    char *end = strchr(quote + 1, '"');
    if (!end) return "127.0.0.1";
 
    size_t len = end - (quote + 1);
    strncpy(result, quote + 1, len);
    result[len] = '\0';
    return result;
}
 
//The definition lives in payload.c.
void print_verse(int chapter, int verse, const char *text);
 
static int send_and_print_impl(const char *payload, int flags)
{
    const int use_local = flags & SEND_FLAG_LOCAL;
    const int quiet     = flags & SEND_FLAG_QUIET;
 
    const char *host = use_local ? "127.0.0.1" : get_ip();
    if (!host) host = "127.0.0.1";
 
    sock_t s;
    struct sockaddr_in addr;
    int n;
 
    s = socket(AF_INET, SOCK_STREAM, 0);
    if ((int)s < 0) {
        if (!quiet) fprintf(stderr, "[Client] Error: could not create socket.\n");
        return 1;
    }
 
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port   = htons(SERVER_PORT);
    if (inet_pton(AF_INET, host, &addr.sin_addr) <= 0) {
        if (!quiet) fprintf(stderr, "[Client] Error: invalid server address.\n");
        CLOSE_SOCKET(s);
        return 1;
    }
    if (connect(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        if (!quiet)
            fprintf(stderr,
                "[Client] Error: Cannot connect to LibQuery server at %s:%d.\n"
                "       Is the server running?  Start it with:\n"
                "       libquery host\n",
                host, SERVER_PORT);
        CLOSE_SOCKET(s);
        return 1;
    }
 
    send(s, payload, (int)strlen(payload), 0);
 
#ifndef _WIN32
    shutdown(s, SHUT_WR);
#endif
 
    char buf[65536];
    int  buf_len = 0;
 
    while ((n = recv(s, buf + buf_len, sizeof(buf) - buf_len - 1, 0)) > 0) {
        buf_len += n;
        buf[buf_len] = '\0';
 
        char *line_start = buf;
        char *newline;
 
        while ((newline = strchr(line_start, '\n')) != NULL) {
            *newline = '\0';
            int chapter, verse;
            char text[4096];
            if (sscanf(line_start, "%d:%d %4095[^\n]", &chapter, &verse, text) == 3)
                print_verse(chapter, verse, text);
            else if (!quiet && *line_start != '\0')
                printf("%s\n", line_start);
 
            line_start = newline + 1;
        }
 
        buf_len = (int)(buf + buf_len - line_start);
        memmove(buf, line_start, buf_len);
    }
 
    if (!quiet && buf_len > 0) {
        buf[buf_len] = '\0';
        int chapter, verse;
        char text[4096];
        if (sscanf(buf, "%d:%d %4095[^\n]", &chapter, &verse, text) == 3)
            print_verse(chapter, verse, text);
        else
            printf("%s\n", buf);
    }
 
    CLOSE_SOCKET(s);
    return 0;
}
 
int send_and_print(const char *payload)
{
    return send_and_print_impl(payload, 0);
}
 
int send_and_print_local(const char *payload)
{
    return send_and_print_impl(payload, SEND_FLAG_LOCAL);
}
 
int send_and_print_quiet(const char *payload)
{
    return send_and_print_impl(payload, SEND_FLAG_QUIET);
}
 
int send_and_print_quiet_local(const char *payload)
{
    return send_and_print_impl(payload, SEND_FLAG_BOTH);
}
 
int ping(bool quiet)
{
    if (quiet)
        return send_and_print_quiet("{\"cmd\":\"ping\",\"flags\":[\"quiet\"]}");
    return send_and_print("{\"cmd\":\"ping\"}");
}
 
int ping_local(void)
{
    return send_and_print_quiet_local("{\"cmd\":\"ping\",\"flags\":[\"quiet\"]}");
}
 
int server_online(void)
{
    return !ping(true);
}