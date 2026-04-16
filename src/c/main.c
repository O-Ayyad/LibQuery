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

#ifndef _WIN32
    #define _POSIX_C_SOURCE 200809L
#endif

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <ctype.h>
#include <sys/stat.h>
#include <unistd.h>

#include "parser_funcs.h"

#define SERVER_PORT 9237
#define LINE_WIDTH  200

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

typedef enum { //Server commands that require authentication
    CMD_CLOSE,
    CMD_HOST,
    CMD_RESTART,
    UNKNOWN,
} Server_Commands;

typedef struct {
    const char *name;
    Server_Commands  cmd;
} CommandEntry;

const CommandEntry COMMANDS[] = {
    {"host",CMD_HOST},
    {"close",CMD_CLOSE},
    {"restart",CMD_RESTART},
};

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

void get_project_root(char *out, size_t size) { //Get the project root for python scripts and tokens
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

#define TOKEN_SUBPATH  "data/serverdata/admin.token"
#define TOKEN_LEN  64

static char token_path[4096];

void resolve_token_path() {
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

//Load the admin token from the token file
char *load_admin_token()
{
    FILE *f = fopen(token_path, "r");
    if (!f) {
        fprintf(stderr, "Error: could not open token file: %s\n", token_path);
        return NULL;
    }

    char *token = malloc(TOKEN_LEN + 1);
    if (!token) {
        fclose(f);
        return NULL;
    }

    if (!fgets(token, TOKEN_LEN + 1, f)) {
        fprintf(stderr, "Error: could not read token\n");
        fclose(f);
        free(token);
        return NULL;
    }
    fclose(f);

    token[strcspn(token, "\r\n")] = '\0';

    if (strlen(token) != TOKEN_LEN) {
        fprintf(stderr, "Error: token malformed (len=%zu)\n", strlen(token));
        free(token);
        return NULL;
    }

    return token;
}

//Get the target IP from the networking config
char* get_ip() {
    static char result[128];
    char config_path[512];
    char project_root[512];
    get_project_root(project_root, sizeof(project_root));

    snprintf(config_path, sizeof(config_path), "%s/data/userdata/networking_config.json", project_root);

    FILE* f = fopen(config_path, "r");
    if (!f) return "127.0.0.1";

    char buf[1024];
    size_t n = fread(buf, 1, sizeof(buf) - 1, f);
    buf[n] = '\0';
    fclose(f);

    char* key = strstr(buf, "\"target_ip\"");
    if (!key) return "127.0.0.1";

    char* colon = strchr(key, ':');
    if (!colon) return "127.0.0.1";

    char* quote = strchr(colon, '"');
    if (!quote) return "127.0.0.1";

    char* end = strchr(quote + 1, '"');
    if (!end) return "127.0.0.1";

    size_t len = end - (quote + 1);
    strncpy(result, quote + 1, len);
    result[len] = '\0';
    return result;
}

//Helper function to print a verse in send_and_print
void print_verse(int chapter, int verse, const char *text) {
    char ref[16];
    snprintf(ref, sizeof(ref), "%d:%-4d ", chapter, verse);
    int ref_len    = strlen(ref);
    int text_width = LINE_WIDTH - ref_len;

    printf("%s", ref);

    int len   = strlen(text);
    int pos   = 0;
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


// Send the payload to the server and prints the return
// Returns 0 on success, 1 on failure.
#define SEND_FLAG_LOCAL 1
#define SEND_FLAG_QUIET 2
#define SEND_FLAG_BOTH 3

static int send_and_print_impl(const char *payload, int flags)
{
    const int use_local = flags & SEND_FLAG_LOCAL;
    const int quiet = flags & SEND_FLAG_QUIET;

    const char *host = use_local ? "127.0.0.1" : get_ip();
    if (!host) host = "127.0.0.1";

    sock_t s;
    struct sockaddr_in addr;
    int n;

    s = socket(AF_INET, SOCK_STREAM, 0);
    if ((int)s < 0) {
        if (!quiet) fprintf(stderr, "Error: could not create socket.\n");
        return 1;
    }

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port   = htons(SERVER_PORT);
    if (inet_pton(AF_INET, host, &addr.sin_addr) <= 0) {
        if (!quiet) fprintf(stderr, "Error: invalid server address.\n");
        CLOSE_SOCKET(s);
        return 1;
    }
    if (connect(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        if (!quiet)
            fprintf(stderr,
                "Error: Cannot connect to LibQuery server at %s:%d.\n"
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
//Only for local commands
int send_and_print_local(const char *payload) {
    return send_and_print_impl(payload, SEND_FLAG_LOCAL);
}
//Send an print but no error message. Used only to check if server is online or not
int send_and_print_quiet(const char *payload) {
    return send_and_print_impl(payload, SEND_FLAG_QUIET);
}
int send_and_print_quiet_local(const char* payload){
     return send_and_print_impl(payload, SEND_FLAG_BOTH);
}
int send_and_print(const char *payload) {
    return send_and_print_impl(payload, 0);
}
int ping(bool quiet) {
    if(quiet){
        return send_and_print_quiet("{\"cmd\":\"ping\",\"flags\":[\"quiet\"]}");
    }
    return send_and_print("{\"cmd\":\"ping\"}");
}
int ping_local() {
    return send_and_print_quiet_local("{\"cmd\":\"ping\",\"flags\":[\"quiet\"]}");    
}
int server_online(){
    return !ping(true);
}

FILE* run_python(char* path, char* args) { //Run a python script
    char exe_path[4096];
    char command[512];

#ifdef _WIN32
    GetModuleFileNameA(NULL, exe_path, sizeof(exe_path));
    char* slash = strrchr(exe_path, '\\');
    if (slash) *slash = '\0';
    snprintf(command, sizeof(command), "py \"%s\\%s\" %s", exe_path, path, args ? args : "");
#else
    ssize_t count = readlink("/proc/self/exe", exe_path, sizeof(exe_path) - 1);
    if (count != -1) exe_path[count] = '\0';
    char* slash = strrchr(exe_path, '/');
    if (slash) *slash = '\0';
    snprintf(command, sizeof(command), "python3 \"%s/%s\" %s", exe_path, path, args ? args : "");
#endif

    return popen(command, "r");
}

int is_safe_path(const char *s) {
    for (const char *p = s; *p; p++) {
        if (*p == '&' || *p == '|' || *p == '^' || *p == '%')
            return 0;
    }
    return 1;
}

int host_server() { //Invoke networking server to host the server in a new terminal
    if(server_online()){
        fprintf(stderr, "Error: Server is already running.\n");
        return 1;
    }
    printf("Starting server.\n");
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

    if (!is_safe_path(exe_path)) {
        fprintf(stderr, "Error: unsafe path detected.\n");
        return 1;
    }
#ifdef _WIN32
    snprintf(command, sizeof(command),
        "start \"LibQuery Server\" cmd /c \"cd /d %s\\src\\python && python -m networking.server\"",
        exe_path);
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

        perror("Error: no terminal emulator found");
        exit(1);
    } else if (pid < 0) {
        fprintf(stderr, "Error: fork failed.\n");
        return -2;
    }
#endif

    int result = system(command);
    if (result != 0) {
        fprintf(stderr, "Error: could not open terminal to host server.\n");
        return -2;
    }

    fflush(stdout);

    printf("Waiting for server to respond...\n\n");

    int waited  = 0;
    int timeout = 30;
    int interval = 500;

    while (waited < timeout * 1000) {
        if (ping_local() == 0)
            break;

    #ifdef _WIN32
        Sleep(interval);
    #else
        usleep(interval * 1000);
    #endif

        waited += interval;

        if (waited % 5000 == 0)
            printf("Still waiting... (%ds)\n", waited / 1000);
    }

    if (waited >= timeout * 1000) {
        fprintf(stderr,
            "Error: server did not respond within %d seconds.\n"
            "       It may have crashed on startup.\n"
            "       Check the server terminal window for error output.\n",
            timeout);
        return 1;
    }
        fprintf(stdout, "Server hosted locally on port %d\n", SERVER_PORT);

    return 0;
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

//Restart the server by closing then hosting
int restart_server(){
    int a = close_server();
    #ifdef _WIN32
    Sleep(2000);
    #else
    sleep(2);
    #endif
    int b = host_server();
    return a || b;
}

//Payload builders
int download(const char *library, const char *book){
    if(!server_online()){
        fprintf(stderr,"Server is not online\n");
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

int download_all(){ // Downloads every book from every library
    if(!server_online()){
        fprintf(stderr,"Server is not online\n");
        return 1;
    }
    char payload[512];

    printf("\n             WARNING! This will download every single book from every library. \n"
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
    snprintf(payload, sizeof(payload), "{\"cmd\":\"download\",\"library\":\"all\"}");
    return send_and_print(payload);
}
//Checks if alias is valid and returns the full reference of the alias
char* resolve_alias(const char *token) { //Local command
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
char* alias(char **args, int argc) { //Local and does not conact server
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
    while (fgets(line, sizeof(line), fp) != NULL){
        strncat(result, line, sizeof(result) - strlen(result) - 1);
    }
    pclose(fp);

    size_t len = strlen(result);
    if (len > 0 && result[len - 1] == '\n')
        result[len - 1] = '\0';

    return result;
}
//libquery target
//libquery target <ip>
//libquery target (local, remove, localhost) all removes the ip and falls back to local
char* target_ip(char* payload){
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
int query(const char *library, const char *book, bool use_range, Range range){ //Query the server for text
    if(!server_online()){
        fprintf(stderr,"Error: Server is not online");
        return 1;
    }
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
            "\"end_verse\":-1}",
            //"\"lang\":\"en\"}",
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
            //"\"lang\":\"en\"}",
            library, book,
            range.start.chapter,
            range.start.verse,    // -1 for no verse
            range.end.chapter,
            range.end.verse);
    }

    return send_and_print(payload);
}

void print_help(void){
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
        "  libquery alias <library>/<book> <alias>      Allows calling of books with an alias (eg. Libquery b genesis 1:1)\n"
        "  libquery target <IP>                         Changes target IP. Use libquery target help for more information."
        "  libquery ls <optional: library>              Lists all available libraries or all available books within a library"
    );
}

static void print_welcome(void){ //Print welcome message
    printf(
        "Welcome to LibQuery, a distributed literary corpus query system\n"
        "Type 'libquery help' for usage.\n"
    );
}
int is_server_command(char* cmd){
    return ((strcasecmp(cmd, "host") ==0)||(strcasecmp(cmd, "close") ==0)||(strcasecmp(cmd, "restart") ==0));
}
Server_Commands parse_command(char *cmd) {
    for (int i = 0; i < (int)(sizeof(COMMANDS) / sizeof(COMMANDS[0])); i++) {
        if (strcasecmp(cmd, COMMANDS[i].name) == 0)
            return COMMANDS[i].cmd;
    }
    return UNKNOWN;
}


int hadoop_available(char *project_root) { //Check if hadoop is available
#ifdef _WIN32
    char path[512];
    struct stat st;

    snprintf(path, sizeof(path), "%s\\hadoop\\bin\\winutils.exe", project_root);
    if (stat(path, &st) == 0) return 1;

    //fall back to system install
    snprintf(path, sizeof(path), "C:\\hadoop\\bin\\winutils.exe");
    return stat(path, &st) == 0;
#else
    return 1;
#endif
}

int is_valid_name(const char *s) {
    if (!s || *s == '\0') return 0;

    for (const char *p = s; *p; p++) {
        if (!isalnum(*p) && *p != '_' && *p != '-') {
            return 0;
        }
    }
    return 1;
}

int main(int argc, char *argv[]){
    if (net_init() != 0) {
        fprintf(stderr, "Error: network initialisation failed.\n");
        return 1;
    }

    char project_root[512];
    get_project_root(project_root, sizeof(project_root));
    resolve_token_path();
    if (!hadoop_available(project_root)) {
        fprintf(stderr,
            "Error: winutils.exe not found.\n"
            "  1. Download hadoop binaries: https://github.com/cdarlint/winutils\n"
            "  2. Place winutils.exe and hadoop.dll in: %s\\hadoop\\bin\\\n",
            project_root
        );
        return 1;
    }

    int rc = 0;
    do{
        if (argc == 1) {
            print_welcome();
            break;
        }
    

        if ((argc == 2) && (is_server_command(argv[1]))){
                
            Server_Commands command = parse_command(argv[1]);


            if(command == UNKNOWN){
                fprintf(stderr, "Error: Unknown command");
                break;
            }
            switch(command){                  
                case CMD_HOST:
                    rc= host_server();
                    break;
                case CMD_CLOSE:
                    if(!server_online()){
                        fprintf(stderr, "Error: Server is not online.\n");
                        break;
                    }
                    rc=close_server();
                    break;
                case CMD_RESTART:
                    if(!server_online()){
                        fprintf(stderr, "Error: Server is not online.\n");
                        break;
                    }
                    rc = restart_server();
                    break;
                default:
                    fprintf(stderr, "Error: Unknown server command\n");
            }   
            break;
        }
        if (argc >= 2 && strcasecmp(argv[1], "ls") == 0) {
            char payload[256];
            if (argc >= 3)
                snprintf(payload, sizeof(payload),
                    "{\"cmd\":\"ls\",\"library\":\"%s\"}", argv[2]);
            else
                snprintf(payload, sizeof(payload), "{\"cmd\":\"ls\"}");
            rc = send_and_print(payload);
            break;
        }
        if (argc >= 2 && (strcasecmp(argv[1], "alias") == 0)){
            if(argc == 2 ){
                fprintf(stderr,
                    "Usage:\n"
                    "  libquery alias add <book or library> <alias>\n"
                    "  libquery alias ls                  Lists all current aliases\n"
                    "  libquery alias rm <alias> or all   Removes aliases\n\n"
                    "Examples:\n"
                    "  libquery alias add genesis g\n"
                    "  libquery bible g 1:1 is now valid!\n"
                    "  libquery alias add bible b\n"
                    "  libquery b g 1:1 is now valid!\n"
                );
                break;
            }
            char *result = alias(&argv[2],argc-2);
            if (result) printf("%s\n", result);
            break;
        }

        if (argc >= 2 && (strcasecmp(argv[1], "target") == 0)){
            if(argc == 2 ){
                target_ip(argv[1]);
                break;
            }
            else if(argc == 3){
                if(strcasecmp(argv[2], "help") == 0){
                    fprintf(stderr,
                    "Usage:\n"
                    "  libquery target                    Prints current target IP\n"
                    "  libquery target <IP Address>       Sets target IP Address\n"
                    "  libquery target rm/remove          Removes target and defaults to localhost 127.0.0.1\n\n"
                    "  libquery target local/localhost    Sets target to localhost"
                );
                break;
                }
                char buf[128];
                snprintf(buf, sizeof(buf), "%s %s", argv[1], argv[2]);
                char* result = target_ip(buf);
                if (result) printf("%s\n", result);
                break;
            }
            else if(argc >= 4){
                fprintf(stderr,"Invalid arguments");
                fprintf(stderr,
                    "Usage:\n"
                    "  libquery target                    Prints current target IP\n"
                    "  libquery target <IP Address>       Sets target IP Address\n"
                    "  libquery target rm/remove          Removes target and defaults to localhost 127.0.0.1\n\n"
                    "  libquery target local/localhost    Sets target to localhost"
                );
                return 1;
            }
            break;
        }
        if (argc == 2 && (strcasecmp(argv[1], "help") == 0 ||
                        strcasecmp(argv[1], "h")   == 0)) {
            print_help();
            break;
        }

        if (argc == 2 && strcasecmp(argv[1], "ping") == 0) {
            rc = ping(false);
            break;
        }

        if (argc >= 2 && strcasecmp(argv[1], "download") == 0) {
            const char *library = (argc >= 3) ? argv[2] : NULL;
            const char *book = (argc >= 4) ? argv[3] : NULL;
            if (!library) {
                fprintf(stderr, "Error: specify a library, e.g. 'libquery download bible'\n");
                rc = 1; 
                break;
            }

            if (!is_valid_name(library) || !is_valid_name(book)) {
                fprintf(stderr, "Error: invalid characters in input.\n");
            return 1;
            }   

            if(strcasecmp(argv[2],"all") == 0){
                download_all();
                break;
            }
            rc = download(library, book);
            break;
        }

        /* Normal query */
        if (argc < 3) {
            fprintf(stderr, "Error: specify library and book.  Try 'libquery help'.\n");
            rc = 1;
            break;
        }
        
        static char library_buf[128];
        static char book_buf[128];

        strncpy(library_buf, resolve_alias(argv[1]), sizeof(library_buf) - 1);
        library_buf[sizeof(library_buf) - 1] = '\0';

        strncpy(book_buf, resolve_alias(argv[2]), sizeof(book_buf) - 1);
        book_buf[sizeof(book_buf) - 1] = '\0';

        const char *library = library_buf;
        const char *book = (argc >= 3) ? book_buf : argv[2];

        const char *ref = (argc >= 4) ? argv[3] : NULL;

        if (strcasecmp(library, "quran") == 0) {
            book = "quran";
            ref  = (argc >= 3) ? argv[2] : NULL;
        }

        bool  use_range = false;
        Range range;
        memset(&range, 0, sizeof(range));
        bool is_single_chapter_lib = (strcasecmp(library, "quran") == 0);

        if (ref) {
            if (!parse_range(ref, &range, is_single_chapter_lib)) {
                fprintf(stderr, "Error: cannot parse reference '%s'.\n", ref);
                rc = 1;
                break;
            }
            use_range = true;
        }
        //printf("DEBUG: final call -> library='%s', book='%s', use_range=%d\n",
        //library, book, use_range);
        rc = query(library, book, use_range, range);
    }while(0);
    
    net_cleanup();
    return rc;
}
