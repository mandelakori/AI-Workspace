#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc != 3 || strlen(argv[1]) > 40) {
        fputs("usage\n", stderr);
        return 2;
    }
    char *end;
    long step = strtol(argv[2], &end, 10);
    if (end == argv[2] || *end || step < 1 || step > 8) {
        fputs("step\n", stderr);
        return 3;
    }
    for (size_t i = 0; i < strlen(argv[1]); i += (size_t)step) putchar(argv[1][i]);
    putchar('\n');
    return 0;
}
