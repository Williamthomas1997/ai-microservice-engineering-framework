package io.github.williamthomas1997.amef.platformrules.fixture.low;

import io.github.williamthomas1997.amef.platformrules.fixture.high.HighLayerService;

/** Fixture: a low-layer type that depends on a high-layer type. The layer rule must report this. */
public class LowLayerService {

    private final HighLayerService upward = new HighLayerService();

    public String call() {
        return upward.describe(new LowLayerValue("x"));
    }
}
