#include "contract.h"
int main(void) {
    int balance = 0;
    char chunk[LINE_CAPACITY];
    while (read_chunk(stdin, chunk)) {
        write_reply(stdout, apply_command(&balance, parse_chunk(chunk)));
    }
    return 0;
}
