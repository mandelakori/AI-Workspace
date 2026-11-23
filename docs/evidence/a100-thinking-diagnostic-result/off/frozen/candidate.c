#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
    size_t slen;
    char *end;
    long step;
    if (argc != 3 || (slen = strlen(argv[1]), slen > 0x28)) {
        fwrite("usage\n", 1, 6, stderr);
        return 2;
    }
    step = strtol(argv[2], &end, 10);
    if (argv[2] != end && *end == '\0' && step > 0 && step < 9) {
        size_t i;
        for (i = 0; i < slen; i += (size_t)step) {
            putchar((int)argv[1][i]);
        }
        putchar(10);
        return 0;
    }
    fwrite("step\n", 1, 5, stderr);
    return 3;
}
