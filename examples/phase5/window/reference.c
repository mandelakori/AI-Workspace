#include <stdio.h>
#include <string.h>
int main(void) {
    char line[80], verb[4], extra;
    int state = 0;
    while (fgets(line, sizeof line, stdin)) {
        int amount = 0;
        if (sscanf(line, "%3s", verb) != 1) continue;
        if (!strcmp(verb, "?") && sscanf(line, "%3s %c", verb, &extra) == 1) {
            printf("%d\n", state);
        } else if ((!strcmp(verb, "+") || !strcmp(verb, "-")) &&
                   sscanf(line, "%3s %d %c", verb, &amount, &extra) == 2 &&
                   0 <= amount && amount <= 50) {
            const int next = state + (!strcmp(verb, "+") ? amount : -amount);
            if (next < 0 || next > 99) puts("limit");
            else { state = next; printf("%d\n", state); }
        } else puts("invalid");
    }
    return 0;
}
