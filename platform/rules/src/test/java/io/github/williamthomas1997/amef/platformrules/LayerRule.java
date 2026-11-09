package io.github.williamthomas1997.amef.platformrules;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.CompositeArchRule;
import java.util.ArrayList;
import java.util.List;

/**
 * Builds the layer rule (spec 2.3): classes of a module of layer N must not depend on classes of any module of
 * layer greater than N. Same-layer and downward dependencies are allowed here; cycles and undeclared
 * dependencies between manifests are checked by {@code tools/manifests.py validate}.
 */
final class LayerRule {

    private LayerRule() {}

    static ArchRule of(List<ModuleManifest> modules) {
        List<ArchRule> rules = new ArrayList<>();
        for (ModuleManifest module : modules) {
            String[] higher = modules.stream()
                    .filter(other -> other.layer() > module.layer())
                    .map(other -> other.basePackage() + "..")
                    .toArray(String[]::new);
            if (higher.length == 0) {
                continue;
            }
            rules.add(noClasses()
                    .that().resideInAPackage(module.basePackage() + "..")
                    .should().dependOnClassesThat().resideInAnyPackage(higher)
                    .as("module '" + module.id() + "' (layer " + module.layer()
                            + ") must not depend on modules of a higher layer")
                    .allowEmptyShould(true));
        }
        if (rules.isEmpty()) {
            throw new IllegalStateException("No layer rules could be built: fewer than two layers in the manifests");
        }
        return CompositeArchRule.of(rules)
                .as("modules depend only on the same or lower layers (spec 2.3)");
    }
}
