#include <stdio.h>
#include "contract.h"

int main(void) {
    int state = 0;
    int delta;
    while (scanf("%d", &delta) == 1) {
        state = meter_step(state, delta);
        printf("%c:%d\n", meter_band(state), state);
    }
    return 0;
}
