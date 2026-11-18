#include "contract.h"
#include <assert.h>
#include <string.h>

int main(void) {
#if defined(FRAMING)
    FILE *file = tmpfile();
    assert(file);
    fputs("one\n", file);
    for (int i = 0; i < 94; ++i) fputc('x', file);
    fputs("yz\nlast", file);
    rewind(file);
    char chunk[LINE_CAPACITY];
    assert(read_chunk(file, chunk) && strcmp(chunk, "one\n") == 0);
    assert(read_chunk(file, chunk) && strlen(chunk) == 95 && chunk[94] == 'y');
    assert(read_chunk(file, chunk) && strcmp(chunk, "z\n") == 0);
    assert(read_chunk(file, chunk) && strcmp(chunk, "last") == 0);
    assert(!read_chunk(file, chunk));
    fclose(file);
#elif defined(SYNTAX)
    assert(parse_chunk(" \t\v\f\r\n").operation == SKIP);
    assert(parse_chunk("").operation == SKIP);
    Command add = parse_chunk("\tadd +031\r\n");
    assert(add.operation == ADD && add.amount == 31);
    Command take = parse_chunk("take -15");
    assert(take.operation == TAKE && take.amount == -15);
    assert(parse_chunk("show \v\f").operation == SHOW);
    assert(parse_chunk("reset").operation == RESET);
    for (const char **item = (const char *[]){"SHOW", "show extra", "add", "add 4 tail",
              "take +", "reset 0", "junk", "add 5.0", "showadd", "add1", "resetreset", NULL};
         *item; ++item) assert(parse_chunk(*item).operation == BAD);
#elif defined(BALANCE)
    int n = 1;
    Reply r = apply_command(&n, (Command){ADD, 1000});
    assert(n == 1001 && r.kind == VALUE && r.value == 1001);
    r = apply_command(&n, (Command){TAKE, 1000});
    assert(n == 1 && r.kind == VALUE && r.value == 1);
    assert(apply_command(&n, (Command){TAKE, 2}).kind == DENIED && n == 1);
    assert(apply_command(&n, (Command){ADD, 1001}).kind == ERROR && n == 1);
    assert(apply_command(&n, (Command){TAKE, -1}).kind == ERROR && n == 1);
    assert(apply_command(&n, (Command){BAD, 0}).kind == ERROR && n == 1);
    assert(apply_command(&n, (Command){SKIP, 0}).kind == QUIET && n == 1);
    n = 10000;
    assert(apply_command(&n, (Command){ADD, 1}).kind == DENIED && n == 10000);
    r = apply_command(&n, (Command){SHOW, 0});
    assert(r.kind == VALUE && r.value == 10000);
    r = apply_command(&n, (Command){RESET, 0});
    assert(r.kind == VALUE && r.value == 0 && n == 0);
#elif defined(OUTPUT)
    FILE *out = tmpfile();
    assert(out);
    write_reply(out, (Reply){QUIET, 0});
    write_reply(out, (Reply){ERROR, 42});
    write_reply(out, (Reply){DENIED, 42});
    write_reply(out, (Reply){VALUE, 512});
    write_reply(out, (Reply){VALUE, 0});
    rewind(out);
    char buffer[64] = "";
    fread(buffer, 1, sizeof(buffer)-1, out);
    assert(strcmp(buffer, "error\ndenied\n512\n0\n") == 0);
    fclose(out);
#endif
    return 0;
}
