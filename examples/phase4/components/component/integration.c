#include <assert.h>
#include <limits.h>
#include "contract.h"

int main(void) {
    assert(clamp_score(INT_MIN) == -20);
    assert(clamp_score(INT_MAX) == 80);
    for (int value = -250; value <= 250; ++value) {
        int clamped = value < -20 ? -20 : value > 80 ? 80 : value;
        assert(clamp_score(value) == clamped);
        int band = value < 0 ? 0 : value < 10 ? 1 : value < 40 ? 2 : 3;
        assert(band_score(clamp_score(value)) == band);
    }
    return 0;
}
