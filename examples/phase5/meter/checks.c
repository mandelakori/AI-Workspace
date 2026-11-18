#include <assert.h>
#include "contract.h"

int main(void) {
#if defined(STATE)
    assert(meter_step(0, -4) == 0);
    assert(meter_step(2, 3) == 5);
    assert(meter_step(8, 10) == 9);
    assert(meter_step(8, -3) == 5);
    assert(meter_step(5, 0) == 5);
#elif defined(BAND)
    assert(meter_band(0) == 'L');
    assert(meter_band(2) == 'L');
    assert(meter_band(3) == 'M');
    assert(meter_band(6) == 'M');
    assert(meter_band(7) == 'H');
    assert(meter_band(9) == 'H');
#endif
    return 0;
}
