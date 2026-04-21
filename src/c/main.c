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
#include <string.h>
#include <stdbool.h>
 
#include "parser_funcs.h"
#include "utils.h"
#include "net.h"
#include "server_handler.h"
#include "local.h"
#include "payload.h"

static void print_welcome(void)
{
    printf("\n\n\n"
        "         <||<------------------------------------------------------------------------------------------------------------------>||>\n"
        "         <||<                  ,,       ,,                                                                                     >||>\n"
        "         <||<  `7MMF'            db      *MM              .g8\"\"8q.                                                             >||>\n"
        "         <||<    MM                       MM            .dP'    `YM.                                                           >||>\n"
        "         <||<    MM            `7MM       MM,dMMb.      dM'      `MM     `7MM  `7MM       .gP\"Ya      `7Mb,od8     `7M'   `MF' >||>\n"
        "         <||<    MM              MM       MM    `Mb     MM        MM       MM    MM      ,M'   Yb       MM' \"'       VA   ,V   >||>\n"
        "         <||<    MM      ,       MM       MM     M8     MM.      ,MP       MM    MM      8M\"\"\"\"\"\"       MM            VA ,V    >||>\n"
        "         <||<    MM     ,M       MM       MM.   ,M9     `Mb.    ,dP'       MM    MM      YM.    ,       MM             VVV     >||>\n"
        "         <||<   .MMmmmmMMM     .JMML.     P^YbmdP'        `\"bmmd\"'         `Mbod\"YML.     `Mbmmd'     .JMML.           ,V      >||>\n"  
        "         <||<                                                MMb                                                     ,V/       >||>\n"
        "         <||<                                                 `qoog'                                                 OOb\"      >||>\n"
        "         <||<------------------------------------------------------------------------------------------------------------------>||>\n"
        "          ASCII art credit: https://patorjk.com/ \n\n"
        "                             |$$|   Welcome to LibQuery, a distributed literary query system.   |$$|\n"
        "                             |$$|            Type 'libquery help' for usage.                    |$$|\n"
    );
}
int main(int argc, char *argv[]){
    if (net_init() != 0) {
        fprintf(stderr, "[Client] Error: network initialisation failed.\n");
        return 1;
    }

    char project_root[512];
    get_project_root(project_root, sizeof(project_root));
    resolve_token_path();
    if (!hadoop_available(project_root)) {
        fprintf(stderr,
            "[Client] Error: winutils.exe not found.\n"
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
                fprintf(stderr, "[Client] Error: Unknown command");
                break;
            }
            switch(command){                  
                case CMD_HOST:
                    rc= host_server();
                    break;
                case CMD_CLOSE:
                    if(!server_online()){
                        fprintf(stderr, "[Client] Error: Server is not online.\n");
                        break;
                    }
                    rc=close_server();
                    break;
                case CMD_RESTART:
                    if(!server_online()){
                        fprintf(stderr, "[Client] Error: Server is not online.\n");
                        break;
                    }
                    rc = restart_server();
                    break;
                default:
                    fprintf(stderr, "[Client] Error: Unknown server command\n");
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
        if (argc >= 3 && strcasecmp(argv[2], "ls" ) == 0 && strcasecmp(argv[1], "alias" ) == 1) { //Allow libquery <library> ls but ignore alias ls
            char payload[256];
            snprintf(payload, sizeof(payload),
                "{\"cmd\":\"ls\",\"library\":\"%s\"}", argv[1]);
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
                fprintf(stderr, "[Client] Error: specify a library, e.g. 'libquery download bible'\n"
                "Try 'libquery help' for all commands");
                rc = 1; 
                break;
            }

            if (!is_valid_name(library) || !is_valid_name(book)) {
                fprintf(stderr, "[Client] Error: invalid characters in input.\n");
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
            fprintf(stderr, "[Client] Error: specify library and book.  Use 'libquery ls' for a list of all libraries\n"
                "Try 'libquery help' for all commands.\n");
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
                fprintf(stderr, "[Client] Error: cannot parse reference '%s'.\n", ref);
                rc = 1;
                break;
            }
            use_range = true;
        }
        if (strcasecmp(library, "talmud") == 0 && use_range && range.start.chapter < 2) {
            fprintf(stderr, "[Client] Error: Talmud chapters start at 2 (e.g. 'libquery talmud niddah 2')\n");
            rc = 1;
            break;
        }
        rc = query(library, book, use_range, range);
    }while(0);
    
    net_cleanup();
    return rc;
}
