/* Approved probe contracts for the reviewed tokenizer and validator split. */
#include "contract.h"

int main(int argc, char **argv) {
    char chunk[LINE_CAPACITY] = {0};
    fread(chunk, 1, sizeof(chunk) - 1, stdin);
#ifdef TOKENIZE
    TokenStream stream = tokenize_chunk(chunk);
    if (stream.count < 0 || stream.count > 3) return 3;
    printf("%d|%d", stream.count, stream.invalid != 0);
    for (int i = 0; i < stream.count; ++i) printf("|%s", stream.words[i]);
    puts("");
#else
    TokenStream stream = tokenize_chunk(chunk);
    Command result = validate_tokens(stream);
    const char *names[] = {"skip", "bad", "add", "take", "reset", "show"};
    if (result.operation < SKIP || result.operation > SHOW) return 3;
    printf("%s", names[result.operation]);
    if (result.operation == ADD || result.operation == TAKE) printf(":%d", result.amount);
    puts("");
#endif
    return 0;
}
