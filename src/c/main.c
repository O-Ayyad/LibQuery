/*
 *   libquery entry point
 *
 *   libquery <library> <book>             Print entire book
 *   libquery <library> <book> <N>         Print chapter N
 *   libquery <library> <book> <N:V>       Print single verse
 *   libquery <library> <book> <N-M>       Print chapter N through end of chapter M
 *   libquery <library> <book> <N:V-M>     Print N:V through end of chapter M
 *   libquery <library> <book> <N-M:V>     Print start of chapter N through M:V
 *   libquery <library> <book> <N:V-M:W>   Print N:V through M:W
 *   libquery download <library> [book]    Download supported libraries
 *   libquery host                         Hosts the server on this machine
 *   libquery ping                         Check server is alive
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <ctype.h>
#include <sys/stat.h>
#include <unistd.h>

#include "parser_funcs.h"

#define SERVER_PORT 9237

#ifdef _WIN32
  #include <winsock2.h>
  #include <ws2tcpip.h>
  #define CLOSE_SOCKET(s) closesocket(s)
  typedef SOCKET sock_t;
#else
  #include <sys/socket.h>
  #include <arpa/inet.h>
  #include <unistd.h>
  #define CLOSE_SOCKET(s) close(s)
  typedef int sock_t;
#endif



// Socket helpers
static int net_init(void)
{
#ifdef _WIN32
    WSADATA wsa;
    return WSAStartup(MAKEWORD(2, 2), &wsa);
#else
    return 0;
#endif
}

static void net_cleanup(void)
{
#ifdef _WIN32
    WSACleanup();
#endif
}


// Send the payload to the server and prints the return
// Returns 0 on success, 1 on failure.
static int send_and_print(const char *payload)
{
    const char *host = getenv("LIBQUERY_HOST");
    if (!host) host = "127.0.0.1";
    sock_t s;
    struct sockaddr_in addr;
    int n;

    s =socket(AF_INET, SOCK_STREAM, 0);
    if ((int)s < 0) {
        fprintf(stderr, "Error: could not create socket.\n");
        return 1;
    }

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port   = htons(SERVER_PORT);
    if (inet_pton(AF_INET, host, &addr.sin_addr) <= 0) {
        fprintf(stderr, "Error: invalid server address.\n");
        CLOSE_SOCKET(s);
        return 1;
    }

    if (connect(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        fprintf(stderr,
            "Error: cannot connect to LibQuery server at %s:%d.\n"
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

    char chunk[4096];
    while ((n = recv(s, chunk, sizeof(chunk) - 1, 0)) > 0) {
        chunk[n] = '\0';
        fputs(chunk, stdout);
    }
    putchar('\n');

    CLOSE_SOCKET(s);
    return 0;
}

int host_server() {
    char exe_path[4096];
    char command[1024];
    
#ifdef _WIN32
    GetModuleFileNameA(NULL, exe_path, sizeof(exe_path));
#else
    ssize_t count = readlink("/proc/self/exe", exe_path, sizeof(exe_path)-1);
    if (count != -1) exe_path[count] = '\0';
#endif

    char *slash = strrchr(exe_path, 
#ifdef _WIN32
        '\\'
#else
        '/'
#endif
    );
    if (slash) {
        *slash = '\0';
    }

#ifdef _WIN32
    snprintf(
        command, sizeof(command),
        "start cmd /k \"cd /d %s\\src\\python && py -m networking.server\"",
        exe_path
    );
#else
    snprintf(
        command, sizeof(command),
        "gnome-terminal -- bash -c 'cd \"%s/src/python\" && python3 -m networking.server; exec bash'",
        exe_path
    );
#endif

    int result = system(command);
    if (result != 0) {
        fprintf(stderr, "Error: could not open terminal to host server.\n");
        return -2;
    }

    return 0;
}

//Payload builders
int ping(void)
{
    return send_and_print("{\"cmd\":\"ping\"}");
}

int download(const char *library, const char *book)
{
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

int query(const char *library, const char *book, bool use_range, Range range)
{
    char payload[1024];
    if (!use_range) {
        // print entire book chapters 1-999
        snprintf(payload, sizeof(payload),
            "{\"cmd\":\"query\","
            "\"library\":\"%s\","
            "\"book\":\"%s\","
            "\"start_chapter\":1,"
            "\"start_verse\":-1,"
            "\"end_chapter\":999,"
            "\"end_verse\":-1,"
            "\"lang\":\"en\"}",
            library, book);
    } else {
        snprintf(payload, sizeof(payload),
            "{\"cmd\":\"query\","
            "\"library\":\"%s\","
            "\"book\":\"%s\","
            "\"start_chapter\":%d,"
            "\"start_verse\":%d,"
            "\"end_chapter\":%d,"
            "\"end_verse\":%d,"
            "\"lang\":\"en\"}",
            library, book,
            range.start.chapter,
            range.start.verse,    // -1 for no verse
            range.end.chapter,
            range.end.verse);
    }

    return send_and_print(payload);
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
        "  libquery quran al-baqarah 2:255\n\n"
        "Other commands:\n"
        "  libquery download bible mark    Downloads a book\n"
        "  libquery download bible         Downloads entire library\n"
        "  libquery host                   Hosts the server\n"
        "  libquery ping                   Check server connection\n"
    );
}

static void print_welcome(void)
{
    printf(
        "Welcome to LibQuery, a distributed literary corpus query system\n"
        "Type 'libquery help' for usage.\n"
    );
}

int main(int argc, char *argv[])
{
    if (net_init() != 0) {
        fprintf(stderr, "Error: network initialisation failed.\n");
        return 1;
    }

    int rc = 0;

    if (argc == 1) {
        print_welcome();
        goto done;
    }
    if (argc == 2 && strcasecmp(argv[1], "host") == 0) {
        rc = host_server();
        goto done;
    }

    if (argc == 2 && (strcasecmp(argv[1], "help") == 0 ||
                      strcasecmp(argv[1], "h")   == 0)) {
        print_help();
        goto done;
    }

    if (argc == 2 && strcasecmp(argv[1], "ping") == 0) {
        rc = ping();
        goto done;
    }

    if (argc >= 2 && strcasecmp(argv[1], "download") == 0) {
        const char *library = (argc >= 3) ? argv[2] : NULL;
        const char *book = (argc >= 4) ? argv[3] : NULL;
        if (!library) {
            fprintf(stderr, "Error: specify a library, e.g. 'libquery download bible'\n");
            rc = 1;
            goto done;
        }
        rc = download(library, book);
        goto done;
    }

    /* Normal query */
    if (argc < 3) {
        fprintf(stderr, "Error: specify library and book.  Try 'libquery help'.\n");
        rc = 1;
        goto done;
    }

    const char *library = argv[1];
    const char *book    = argv[2];
    const char *ref     = (argc >= 4) ? argv[3] : NULL;

    bool  use_range = false;
    Range range;
    memset(&range, 0, sizeof(range));

    if (ref) {
        if (!parse_range(ref, &range)) {
            fprintf(stderr, "Error: cannot parse reference '%s'.\n", ref);
            rc = 1;
            goto done;
        }
        use_range = true;
    }

    rc = query(library, book, use_range, range);

done:
    net_cleanup();
    return rc;
}
