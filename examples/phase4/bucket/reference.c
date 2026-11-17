#include <stdio.h>

int clamp_score(int value) {
    if (value < -20) return -20;
    if (value > 80) return 80;
    return value;
}

int band_score(int value) {
    if (value < 0) return 0;
    if (value < 10) return 1;
    if (value < 40) return 2;
    return 3;
}

int main(void) {
    int value;
    char extra;
    if (scanf("%d", &value) != 1 || scanf(" %c", &extra) == 1) {
        fputs("invalid\n", stderr);
        return 2;
    }
    int score = clamp_score(value);
    printf("%d:%d\n", score, band_score(score));
    return 0;
}
