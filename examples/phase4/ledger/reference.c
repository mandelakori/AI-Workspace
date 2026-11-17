#include <stdio.h>
#include <string.h>

int main(void) {
    char line[96], op[20], tail;
    int balance = 0;
    while (fgets(line, sizeof line, stdin)) {
        int value;
        if (sscanf(line, " %19s", op) != 1) continue;
        if (sscanf(line, " %19s %d %c", op, &value, &tail) == 2 &&
            (strcmp(op, "add") == 0 || strcmp(op, "take") == 0)) {
            if (value < 0 || value > 1000) { puts("error"); continue; }
            int next = balance + (strcmp(op, "add") == 0 ? value : -value);
            if (next < 0 || next > 10000) puts("denied");
            else { balance = next; printf("%d\n", balance); }
        } else if (sscanf(line, " %19s %c", op, &tail) == 1 && strcmp(op, "reset") == 0) {
            balance = 0;
            puts("0");
        } else if (sscanf(line, " %19s %c", op, &tail) == 1 && strcmp(op, "show") == 0) {
            printf("%d\n", balance);
        } else puts("error");
    }
    return 0;
}
