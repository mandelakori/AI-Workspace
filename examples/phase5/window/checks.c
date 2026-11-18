#include "contract.h"
#include <assert.h>
int main(void) {
#ifdef SYNTAX
    Input x = parse_window(" \t+ 15\n");
    assert(x.kind == PLUS && x.amount == 15);
    x = parse_window("- 0");
    assert(x.kind == MINUS && x.amount == 0);
    assert(parse_window("\v\f").kind == BLANK);
    assert(parse_window("?\t ").kind == QUERY);
    assert(parse_window("+9").kind == BAD);
    assert(parse_window("? 0").kind == BAD);
    assert(parse_window("+ 4 trailing").kind == BAD);
    assert(parse_window("+ -4").kind == BAD);
    assert(parse_window("- 51").kind == BAD);
    assert(parse_window("N").kind == BAD);
#elif defined(STATE)
    int n = 92;
    assert(step_window(&n, (Input){PLUS,8}).kind == LIMIT && n == 92);
    Effect e = step_window(&n, (Input){PLUS,7});
    assert(e.kind == NUMBER && e.value == 99 && n == 99);
    e = step_window(&n, (Input){MINUS,50});
    assert(e.kind == NUMBER && e.value == 49 && n == 49);
    assert(step_window(&n, (Input){MINUS,50}).kind == LIMIT && n == 49);
    assert(step_window(&n, (Input){BAD,0}).kind == INVALID && n == 49);
    assert(step_window(&n, (Input){BLANK,0}).kind == SILENT && n == 49);
    e = step_window(&n, (Input){QUERY,0});
    assert(e.kind == NUMBER && e.value == 49 && n == 49);
#endif
    return 0;
}
