#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "usage\n");
        return 2;
    }
    long step = strtol(argv[2], NULL, 10);
    size_t len = strlen(argv[1]);
    if (len > 0 && step > (long)len) {
        fprintf(stderr, "step\n");
        return 3;
    }
    for (size_t i = 0; i < len; i += step) {
        putchar(argv[1][i]);
    }
    putchar('\n');
    return 0;
}
