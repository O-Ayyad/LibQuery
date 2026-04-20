#ifndef UTIL_H
#define UTIL_H

#include <stddef.h>

void get_project_root(char *out, size_t size);
void resolve_token_path(void);
char *load_admin_token(void);
int is_valid_name(const char *s);
int is_valid_keyword(const char *s);
int hadoop_available(char *project_root);

#endif
