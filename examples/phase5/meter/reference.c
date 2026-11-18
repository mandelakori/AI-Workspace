#include <stdio.h>
int main(void) {
    int delta;
    long long state = 0;
    while (scanf("%d", &delta) == 1) {
        state += delta;
        if (state > 9) state = 9;
        if (state < 0) state = 0;
        const char band = state < 3 ? 'L' : state < 7 ? 'M' : 'H';
        printf("%c:%d\n", band, (int)state);
    }
    return 0;
}
