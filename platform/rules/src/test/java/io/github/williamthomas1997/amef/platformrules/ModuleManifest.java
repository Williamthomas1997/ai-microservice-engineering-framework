package io.github.williamthomas1997.amef.platformrules;

import java.io.IOException;
import java.io.Reader;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.Yaml;
import org.yaml.snakeyaml.constructor.SafeConstructor;

/**
 * One module manifest ({@code brick.yaml} or {@code module.yaml}): the fields the layer rule needs.
 *
 * @param id manifest id, e.g. {@code redis}
 * @param layer layer number from spec 2.3 (1 = foundation ... 5 = apps and qa)
 * @param basePackage Java package that holds all classes of the module (and its stack sub-modules)
 * @param source manifest file, for error messages
 */
record ModuleManifest(String id, int layer, String basePackage, Path source) {

    static final String REPO_ROOT_PROPERTY = "amef.repo.root";

    /** Manifest locations relative to the repository root, as documented in docs/IMPLEMENTATION_PLAN.md. */
    private static final List<String> MANIFEST_GLOBS =
            List.of("foundation/*/module.yaml", "bricks/*/brick.yaml", "apps/*/module.yaml", "qa/module.yaml");

    static Path repoRoot() {
        String root = System.getProperty(REPO_ROOT_PROPERTY);
        if (root == null || root.isBlank()) {
            throw new IllegalStateException("System property '" + REPO_ROOT_PROPERTY
                    + "' is not set; run the tests through Maven (platform/rules/pom.xml sets it).");
        }
        return Path.of(root).toAbsolutePath().normalize();
    }

    static List<ModuleManifest> loadAll(Path repoRoot) {
        List<ModuleManifest> result = new ArrayList<>();
        for (String glob : MANIFEST_GLOBS) {
            var matcher = repoRoot.getFileSystem().getPathMatcher("glob:" + glob);
            try (Stream<Path> files = Files.walk(repoRoot, 3)) {
                files.filter(p -> matcher.matches(repoRoot.relativize(p)))
                        .sorted(Comparator.naturalOrder())
                        .forEach(p -> result.add(load(p)));
            } catch (IOException e) {
                throw new UncheckedIOException("Cannot scan " + repoRoot + " for " + glob, e);
            }
        }
        return List.copyOf(result);
    }

    static ModuleManifest load(Path file) {
        Yaml yaml = new Yaml(new SafeConstructor(new LoaderOptions()));
        try (Reader reader = Files.newBufferedReader(file)) {
            Object loaded = yaml.load(reader);
            if (!(loaded instanceof Map<?, ?> map)) {
                throw new IllegalStateException(file + ": expected a YAML mapping");
            }
            return new ModuleManifest(
                    requireString(map, "id", file),
                    requireInt(map, "layer", file),
                    requireString(map, "package", file),
                    file);
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot read " + file, e);
        }
    }

    private static String requireString(Map<?, ?> map, String key, Path file) {
        if (map.get(key) instanceof String value && !value.isBlank()) {
            return value;
        }
        throw new IllegalStateException(file + ": missing or empty '" + key + "'");
    }

    private static int requireInt(Map<?, ?> map, String key, Path file) {
        if (map.get(key) instanceof Integer value) {
            return value;
        }
        throw new IllegalStateException(file + ": '" + key + "' must be an integer");
    }
}
