package io.github.williamthomas1997.amef.platformrules.fixture.high;

import io.github.williamthomas1997.amef.platformrules.fixture.low.LowLayerValue;

/** Fixture: a high-layer type that depends on a low-layer type. The layer rule must accept this. */
public class HighLayerService {

    private LowLayerValue last;

    public String describe(LowLayerValue value) {
        last = value;
        return last.value();
    }
}
