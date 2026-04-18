#ifndef SERVER_H
#define SERVER_H

typedef enum {
    CMD_CLOSE,
    CMD_HOST,
    CMD_RESTART,
    UNKNOWN,
} Server_Commands;

Server_Commands parse_command(char *cmd);
int is_server_command(char *cmd);

int host_server(void);
int close_server(void);
int restart_server(void);

#endif
