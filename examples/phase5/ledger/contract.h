#ifndef LEDGER_CONTRACT_H
#define LEDGER_CONTRACT_H
#include <stdio.h>
#include <ctype.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
enum { LINE_CAPACITY = 96 };
typedef enum { SKIP, BAD, ADD, TAKE, RESET, SHOW } Operation;
typedef struct { Operation operation; int amount; } Command;
typedef enum { QUIET, ERROR, DENIED, VALUE } ReplyKind;
typedef struct { ReplyKind kind; int value; } Reply;
int read_chunk(FILE *input, char chunk[LINE_CAPACITY]);
Command parse_chunk(const char *chunk);
Reply apply_command(int *balance, Command command);
void write_reply(FILE *output, Reply reply);
#endif
