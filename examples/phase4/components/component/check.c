#include <assert.h>
#include <limits.h>
#include "contract.h"

int main(void) {
#if defined(CLAMP)
    assert(clamp_score(-100) == -20);
    assert(clamp_score(10) == 10);
    assert(clamp_score(99) == 80);
#elif defined(BAND)
    assert(band_score(-2) == 0);
    assert(band_score(3) == 1);
    assert(band_score(20) == 2);
    assert(band_score(70) == 3);
#endif
    return 0;
}
