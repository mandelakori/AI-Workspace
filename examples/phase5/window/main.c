#include "contract.h"
#include <stdio.h>
int main(void) {
    int state = 0;
    char line[80];
    while (fgets(line, sizeof line, stdin)) {
        Effect effect = step_window(&state, parse_window(line));
        if (effect.kind == INVALID) puts("invalid");
        if (effect.kind == LIMIT) puts("limit");
        if (effect.kind == NUMBER) printf("%d\n", effect.value);
    }
    return 0;
}
