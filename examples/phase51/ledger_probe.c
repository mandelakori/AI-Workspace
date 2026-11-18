/* Public driver for one ledger component. Reference implementation stays in its own stage. */
#include "contract.h"
#if defined(FRAMING)
int main(void) {
    char buffer[LINE_CAPACITY];
    while (read_chunk(stdin, buffer)) {
        for (size_t i = 0; buffer[i] != '\0'; ++i) printf("%02x", (unsigned char)buffer[i]);
        puts("");
    }
    return 0;
}
#elif defined(SYNTAX)
int main(void) {
    char text[LINE_CAPACITY];
    const char *names[] = {"skip", "bad", "add", "take", "reset", "show"};
    size_t count = fread(text, 1, sizeof(text) - 1, stdin);
    text[count] = '\0';
    Command result = parse_chunk(text);
    if (result.operation < SKIP || result.operation > SHOW) return 3;
    printf("%s", names[result.operation]);
    if (result.operation == ADD || result.operation == TAKE) printf(":%d", result.amount);
    puts("");
    return 0;
}
#elif defined(BALANCE)
int main(int argc, char **argv) {
    const char *names[] = {"quiet", "error", "denied", "value"};
    int operation, amount, balance;
    if (argc != 2 || sscanf(argv[1], "%d", &balance) != 1) return 3;
    while (scanf("%d %d", &operation, &amount) == 2) {
        Reply reply = apply_command(&balance, (Command){operation, amount});
        if (reply.kind < QUIET || reply.kind > VALUE) return 3;
        printf("%s:%d", names[reply.kind], balance);
        if (reply.kind == VALUE) printf(":%d", reply.value);
        puts("");
    }
    return 0;
}
#endif
