#ifndef NET_H
#define NET_H

#include <stdbool.h>

int net_init(void);
void net_cleanup(void);

char *get_ip(void);

//Sends the payload to the configured remote server and prints the response
int send_and_print(const char *payload);

//send_and_print() but only connects to 127.0.0.1
int send_and_print_local(const char *payload);

// send_and_print() but suppresses all error output
int send_and_print_quiet(const char *payload);

int send_and_print_quiet_local(const char *payload);
int send_and_print_with_library(const char *payload, const char *library);

// Returns 0 if the server respondes
int ping(bool quiet);
int ping_local(void);
int server_online(void);

#endif
