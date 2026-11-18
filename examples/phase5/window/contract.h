#ifndef WINDOW_CONTRACT_H
#define WINDOW_CONTRACT_H
#include <stdio.h>
#include <ctype.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
typedef enum { BLANK, BAD, PLUS, MINUS, QUERY } Kind;
typedef struct {Kind kind; int amount;} Input;
typedef enum {SILENT, INVALID, LIMIT, NUMBER} EffectKind;
typedef struct {EffectKind kind; int value;} Effect;
Input parse_window(const char *text);
Effect step_window(int *state, Input input);
#endif
