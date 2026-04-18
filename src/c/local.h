#ifndef LOCAL_H
#define LOCAL_H

FILE *run_python(char *path, char *args);

// Returns 1 if string contains no shell-injection characters

int is_safe_path(const char *s);
char *resolve_alias(const char *token);
char *alias(char **args, int argc);

//Reads and sets the target IP
char *target_ip(char *payload);

#endif 
