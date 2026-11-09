package io.github.williamthomas1997.amef.platformrules;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.lang.EvaluationResult;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

class LayerRuleTest {

    private static final String BASE_PACKAGE = "io.github.williamthomas1997.amef";
    private static final String FIXTURE_PACKAGE = BASE_PACKAGE + ".platformrules.fixture";

    private static List<ModuleManifest> manifests;

    @BeforeAll
    static void loadManifests() {
        manifests = ModuleManifest.loadAll(ModuleManifest.repoRoot());
    }

    @Test
    void everyPlannedModuleHasAManifest() {
        Set<String> ids = manifests.stream().map(ModuleManifest::id).collect(Collectors.toSet());

        assertThat(ids).contains(
                "contracts", "architecture-guard", "test-support",
                "observability", "redis", "messaging", "resilience", "external-call", "cache-sync",
                "gateway", "audit-service", "sample-service-reactive", "sample-service-servlet", "qa");
        assertThat(manifests).allSatisfy(m -> {
            assertThat(m.layer()).as(m.id() + " layer").isBetween(1, 5);
            assertThat(m.basePackage()).as(m.id() + " package").startsWith(BASE_PACKAGE + ".");
        });
    }

    @Test
    void modulePackagesDoNotOverlap() {
        for (ModuleManifest a : manifests) {
            for (ModuleManifest b : manifests) {
                if (a != b) {
                    assertThat(a.basePackage() + ".")
                            .as("package of %s must not contain package of %s", b.id(), a.id())
                            .doesNotStartWith(b.basePackage() + ".");
                }
            }
        }
    }

    @Test
    void noPlatformModuleDependsOnAHigherLayer() {
        JavaClasses platformClasses = new ClassFileImporter()
                .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
                .importPackages(BASE_PACKAGE);

        LayerRule.of(manifests).check(platformClasses);
    }

    @Test
    void ruleReportsAnUpwardDependency() {
        EvaluationResult result = LayerRule.of(fixtureModules()).evaluate(fixtureClasses());

        assertThat(result.hasViolation()).isTrue();
        assertThat(result.getFailureReport().getDetails())
                .anySatisfy(line -> assertThat(line).contains("LowLayerService").contains("HighLayerService"));
    }

    @Test
    void ruleAcceptsADownwardDependency() {
        // Only the high-layer fixture (which uses the low layer in a field, a parameter and a method call) is checked.
        JavaClasses highOnly = new ClassFileImporter().importPackages(FIXTURE_PACKAGE + ".high");

        EvaluationResult result = LayerRule.of(fixtureModules()).evaluate(highOnly);

        assertThat(highOnly).isNotEmpty();
        assertThat(result.hasViolation()).as(result.getFailureReport().toString()).isFalse();
    }

    private static List<ModuleManifest> fixtureModules() {
        return List.of(
                new ModuleManifest("low", 1, FIXTURE_PACKAGE + ".low", Path.of("fixture-low.yaml")),
                new ModuleManifest("high", 3, FIXTURE_PACKAGE + ".high", Path.of("fixture-high.yaml")));
    }

    private static JavaClasses fixtureClasses() {
        return new ClassFileImporter().importPackages(FIXTURE_PACKAGE);
    }
}
