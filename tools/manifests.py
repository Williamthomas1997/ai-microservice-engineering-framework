#!/usr/bin/env python3
"""Validate module manifests and generate documentation from them.

Manifests are the single source of truth for the module catalogue (spec 3):

    foundation/*/module.yaml   layer 1
    bricks/*/brick.yaml        layers 2-4
    apps/*/module.yaml         layer 5
    qa/module.yaml             layer 5 (standalone Maven project, not in the reactor)

Usage:
    python tools/manifests.py validate              # exit 1 and list problems if anything is wrong
    python tools/manifests.py generate              # rewrite the generated blocks in README.md and docs/architecture.md
    python tools/manifests.py generate --check      # exit 1 if a generated block is out of date (CI)

Options:
    --root PATH   repository root (default: the parent of this file's directory)
"""
from __future__ import annotations

import argparse
import dataclasses
import pathlib
import sys
import xml.etree.ElementTree as ET

import yaml

BASE_PACKAGE = "io.github.williamthomas1997.amef"
GROUP_ID = "io.github.williamthomas1997"
MANIFEST_GLOBS = ("foundation/*/module.yaml", "bricks/*/brick.yaml", "apps/*/module.yaml", "qa/module.yaml")
STANDALONE_KINDS = {"qa"}  # built on their own, never listed in the root reactor
LAYERS_BY_KIND = {"foundation": {1}, "brick": {2, 3, 4}, "app": {5}, "qa": {5}}
LAYER_NAMES = {1: "L1 foundation", 2: "L2 observability", 3: "L3 infrastructure bricks",
               4: "L4 integration bricks", 5: "L5 apps and qa"}
REQUIRED_FIELDS = {
    "id": str, "kind": str, "layer": int, "description": str, "package": str, "artifacts": dict,
    "provides": list, "requires": list, "infra": list, "bans": list, "config-prefix": str,
    "status": str, "milestone": str,
}
STATUSES = {"planned", "in-progress", "done"}
BRICK_STACKS = ["reactive", "servlet"]
BANS_START, BANS_END = "<!-- amef:bans:start -->", "<!-- amef:bans:end -->"
CATALOGUE_START, CATALOGUE_END = "<!-- amef:catalogue:start -->", "<!-- amef:catalogue:end -->"
GRAPH_START, GRAPH_END = "<!-- amef:graph:start -->", "<!-- amef:graph:end -->"
POM_NS = {"m": "http://maven.apache.org/POM/4.0.0"}


@dataclasses.dataclass(frozen=True)
class Manifest:
    path: pathlib.Path
    data: dict

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def layer(self) -> int:
        return self.data["layer"]

    @property
    def kind(self) -> str:
        return self.data["kind"]

    @property
    def directory(self) -> pathlib.Path:
        return self.path.parent

    @property
    def artifacts(self) -> list[str]:
        return list(self.data["artifacts"].values())


@dataclasses.dataclass(frozen=True)
class Pom:
    path: pathlib.Path
    artifact_id: str
    dependencies: list[tuple[str, str]]  # (groupId, artifactId)
    modules: list[str]


# --------------------------------------------------------------------------------------------- loading

def load_manifests(root: pathlib.Path) -> list[Manifest]:
    manifests = []
    for pattern in MANIFEST_GLOBS:
        for path in sorted(root.glob(pattern)):
            with path.open(encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
            manifests.append(Manifest(path, data if isinstance(data, dict) else {}))
    return manifests


def read_pom(path: pathlib.Path) -> Pom:
    tree = ET.parse(path).getroot()

    def text(element, tag):
        child = element.find(f"m:{tag}", POM_NS)
        return child.text.strip() if child is not None and child.text else ""

    dependencies = [(text(d, "groupId"), text(d, "artifactId"))
                    for d in tree.findall("m:dependencies/m:dependency", POM_NS)]
    modules = [m.text.strip() for m in tree.findall("m:modules/m:module", POM_NS) if m.text]
    return Pom(path, text(tree, "artifactId"), dependencies, modules)


def poms_under(directory: pathlib.Path) -> list[Pom]:
    """pom.xml files in the directory itself and up to two levels below (brick/<stack>/pom.xml)."""
    found = []
    for pattern in ("pom.xml", "*/pom.xml", "*/*/pom.xml"):
        found.extend(sorted(directory.glob(pattern)))
    return [read_pom(p) for p in found if "target" not in p.parts]


# --------------------------------------------------------------------------------------------- validation

def validate(root: pathlib.Path) -> list[str]:
    manifests = load_manifests(root)
    if not manifests:
        return [f"no manifests found under {root} ({', '.join(MANIFEST_GLOBS)})"]

    errors = []
    for m in manifests:
        errors.extend(_check_schema(root, m))
    if errors:
        return errors  # the remaining checks assume well-formed manifests

    by_id: dict[str, Manifest] = {}
    for m in manifests:
        if m.id in by_id:
            errors.append(f"{_rel(root, m.path)}: duplicate id '{m.id}' (also in {_rel(root, by_id[m.id].path)})")
        by_id[m.id] = m
    errors.extend(_check_packages(root, manifests))
    errors.extend(_check_unique_artifacts(root, manifests))
    errors.extend(_check_requires(root, manifests, by_id))
    errors.extend(_check_cycles(by_id))
    errors.extend(_check_poms(root, manifests, by_id))
    errors.extend(_check_bans(root, manifests))
    errors.extend(_check_bom_and_rules(root, manifests))
    return errors


def _check_bom_and_rules(root: pathlib.Path, manifests: list[Manifest]) -> list[str]:
    """Library artifacts are managed by the BOM; every reactor artifact is on the platform-rules classpath (so the
    ArchUnit layer rule sees it); every brick has a README."""
    errors = []
    bom = root / "bom" / "pom.xml"
    rules = root / "platform" / "rules" / "pom.xml"
    managed = set()
    if bom.is_file():
        tree = ET.parse(bom).getroot()
        managed = {d.findtext("m:artifactId", "", POM_NS).strip()
                   for d in tree.findall("m:dependencyManagement/m:dependencies/m:dependency", POM_NS)}
    else:
        errors.append("bom/pom.xml not found")
    on_rules_classpath = {a for _, a in read_pom(rules).dependencies} if rules.is_file() else set()
    if not rules.is_file():
        errors.append("platform/rules/pom.xml not found")
    for m in manifests:
        where = _rel(root, m.path)
        if m.kind in ("foundation", "brick"):
            for artifact in m.artifacts:
                if artifact not in managed:
                    errors.append(f"{where}: artifact '{artifact}' is not managed in bom/pom.xml")
        if m.kind not in STANDALONE_KINDS:
            for artifact in m.artifacts:
                if artifact not in on_rules_classpath:
                    errors.append(f"{where}: artifact '{artifact}' is missing from platform/rules/pom.xml, "
                                  "so the layer rule would not check it")
        if m.kind == "brick" and not (m.directory / "README.md").is_file():
            errors.append(f"{where}: brick has no README.md")
    return errors


def _rel(root: pathlib.Path, path: pathlib.Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _check_schema(root: pathlib.Path, m: Manifest) -> list[str]:
    where = _rel(root, m.path)
    errors = []
    for field, expected in REQUIRED_FIELDS.items():
        value = m.data.get(field)
        if value is None:
            errors.append(f"{where}: missing field '{field}'")
        elif not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            errors.append(f"{where}: field '{field}' must be a {expected.__name__}")
    if errors:
        return errors

    kind = m.kind
    if kind not in LAYERS_BY_KIND:
        errors.append(f"{where}: unknown kind '{kind}' (expected one of {sorted(LAYERS_BY_KIND)})")
    elif m.layer not in LAYERS_BY_KIND[kind]:
        errors.append(f"{where}: a {kind} must be on layer {sorted(LAYERS_BY_KIND[kind])}, not {m.layer}")
    if m.id != m.directory.name:
        errors.append(f"{where}: id '{m.id}' must equal the folder name '{m.directory.name}'")
    if not m.data["package"].startswith(BASE_PACKAGE + "."):
        errors.append(f"{where}: package must start with '{BASE_PACKAGE}.'")
    if not m.data["config-prefix"].startswith("amef."):
        errors.append(f"{where}: config-prefix must start with 'amef.'")
    if m.data["status"] not in STATUSES:
        errors.append(f"{where}: status must be one of {sorted(STATUSES)}")
    for field in ("provides", "requires", "infra", "bans"):
        if not all(isinstance(item, str) for item in m.data[field]):
            errors.append(f"{where}: every entry of '{field}' must be a string")
    if kind == "brick":
        if m.data.get("stacks") != BRICK_STACKS:
            errors.append(f"{where}: a brick must declare stacks: [reactive, servlet]")
        expected = {s: f"amef-{m.id}-{s}" for s in ("core", "reactive", "servlet")}
        if m.data["artifacts"] != expected:
            errors.append(f"{where}: brick artifacts must be {expected}")
    elif not all(isinstance(a, str) and a.startswith("amef-") for a in m.data["artifacts"].values()):
        errors.append(f"{where}: artifacts must be artifactIds starting with 'amef-'")
    return errors


def _check_packages(root: pathlib.Path, manifests: list[Manifest]) -> list[str]:
    """Packages must be unique and must not nest, so every class belongs to exactly one module."""
    errors = []
    for a in manifests:
        for b in manifests:
            if a is b:
                continue
            pkg_a, pkg_b = a.data["package"], b.data["package"]
            if pkg_a == pkg_b and a.path < b.path:
                errors.append(f"{_rel(root, b.path)}: package '{pkg_b}' already used by '{a.id}'")
            elif pkg_b.startswith(pkg_a + "."):
                errors.append(f"package of '{b.id}' ({pkg_b}) is nested inside the package of '{a.id}' ({pkg_a})")
    return errors


def _check_unique_artifacts(root: pathlib.Path, manifests: list[Manifest]) -> list[str]:
    owner: dict[str, str] = {}
    errors = []
    for m in manifests:
        for artifact in m.artifacts:
            if artifact in owner:
                errors.append(f"{_rel(root, m.path)}: artifact '{artifact}' already declared by '{owner[artifact]}'")
            owner[artifact] = m.id
    return errors


def _check_requires(root: pathlib.Path, manifests: list[Manifest], by_id: dict[str, Manifest]) -> list[str]:
    errors = []
    for m in manifests:
        for required in m.data["requires"]:
            target = by_id.get(required)
            if target is None:
                errors.append(f"{_rel(root, m.path)}: requires unknown module '{required}'")
            elif target is m:
                errors.append(f"{_rel(root, m.path)}: requires itself")
            elif target.layer > m.layer:
                errors.append(f"{_rel(root, m.path)}: '{m.id}' (layer {m.layer}) requires '{required}' "
                              f"(layer {target.layer}); dependencies must point to the same or a lower layer")
    return errors


def _check_cycles(by_id: dict[str, Manifest]) -> list[str]:
    white, grey, black = 0, 1, 2
    colour = {key: white for key in by_id}
    errors: list[str] = []

    def visit(node: str, stack: list[str]) -> None:
        colour[node] = grey
        stack.append(node)
        for nxt in by_id[node].data["requires"]:
            if nxt not in by_id:
                continue
            if colour[nxt] == grey:
                cycle = stack[stack.index(nxt):] + [nxt]
                errors.append("dependency cycle: " + " -> ".join(cycle))
            elif colour[nxt] == white:
                visit(nxt, stack)
        stack.pop()
        colour[node] = black

    for key in sorted(by_id):
        if colour[key] == white:
            visit(key, [])
    return errors


def _check_poms(root: pathlib.Path, manifests: list[Manifest], by_id: dict[str, Manifest]) -> list[str]:
    errors = []
    root_pom_path = root / "pom.xml"
    if not root_pom_path.is_file():
        return [f"missing root pom.xml in {root}"]
    reactor = {(root / module).resolve() for module in read_pom(root_pom_path).modules}
    artifact_owner = {a: m for m in manifests for a in m.artifacts}

    for m in manifests:
        where = _rel(root, m.path)
        poms = [p for p in poms_under(m.directory) if p.path.parent.resolve() != root.resolve()]
        if m.kind == "brick":
            # The brick folder holds only the stack modules; core/reactive/servlet are the real modules.
            poms = [p for p in poms if p.path.parent != m.directory]
        found = {p.artifact_id: p for p in poms}
        for artifact in m.artifacts:
            if artifact not in found:
                errors.append(f"{where}: artifact '{artifact}' has no pom.xml under {_rel(root, m.directory)}/")
        for pom in poms:
            pom_where = _rel(root, pom.path)
            if pom.artifact_id not in m.artifacts:
                errors.append(f"{pom_where}: artifactId '{pom.artifact_id}' is not declared in {where}")
                continue
            in_reactor = pom.path.parent.resolve() in reactor
            if m.kind in STANDALONE_KINDS and in_reactor:
                errors.append(f"{pom_where}: a {m.kind} project must not be listed in the root pom.xml modules")
            if m.kind not in STANDALONE_KINDS and not in_reactor:
                errors.append(f"{pom_where}: module is missing from the root pom.xml <modules>")
            allowed = {m.id, *m.data["requires"]}
            for group, artifact in pom.dependencies:
                if group != GROUP_ID or artifact not in artifact_owner:
                    continue
                target = artifact_owner[artifact]
                if target.id not in allowed:
                    errors.append(f"{pom_where}: depends on '{artifact}' of module '{target.id}', "
                                  f"which is not in requires of '{m.id}' ({where})")
    return errors


def _check_bans(root: pathlib.Path, manifests: list[Manifest]) -> list[str]:
    build_parent = root / "build-parent" / "pom.xml"
    if not build_parent.is_file():
        return ["build-parent/pom.xml not found; cannot check the enforcer bans"]
    text = build_parent.read_text(encoding="utf-8")
    if BANS_START not in text or BANS_END not in text:
        return [f"build-parent/pom.xml: missing {BANS_START} / {BANS_END} markers"]
    block = text.split(BANS_START, 1)[1].split(BANS_END, 1)[0]
    enforced = set()
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("<exclude>") and line.endswith("</exclude>"):
            coordinates = line[len("<exclude>"):-len("</exclude>")]
            enforced.add(coordinates.split(":")[1] if ":" in coordinates else coordinates)
    declared = {ban for m in manifests for ban in m.data["bans"]}
    errors = []
    for missing in sorted(declared - enforced):
        errors.append(f"build-parent/pom.xml: ban '{missing}' declared in a manifest is not enforced")
    for extra in sorted(enforced - declared):
        errors.append(f"build-parent/pom.xml: ban '{extra}' is enforced but declared in no manifest")
    return errors


# --------------------------------------------------------------------------------------------- generation

def catalogue_table(root: pathlib.Path, manifests: list[Manifest]) -> str:
    rows = ["| Layer | Module | Kind | Artifacts | Provides | Requires | Infra | Status |",
            "|---|---|---|---|---|---|---|---|"]
    for m in sorted(manifests, key=lambda x: (x.layer, _kind_order(x.kind), x.id)):
        d = m.data
        rows.append("| {layer} | {link} | {kind} | {artifacts} | {provides} | {requires} | {infra} | {status} |".format(
            layer=f"L{m.layer}",
            link=f"[`{m.id}`]({_rel(root, m.directory)}/)",
            kind=m.kind,
            artifacts=", ".join(f"`{a}`" for a in m.artifacts),
            provides=", ".join(d["provides"]) or "-",
            requires=", ".join(d["requires"]) or "-",
            infra=", ".join(d["infra"]) or "-",
            status=f"{d['status']} ({d['milestone']})",
        ))
    return "\n".join(rows)


def _kind_order(kind: str) -> int:
    return ["foundation", "brick", "app", "qa"].index(kind) if kind in LAYERS_BY_KIND else 99


def dependency_graph(manifests: list[Manifest]) -> str:
    """Mermaid flowchart of `requires`, transitively reduced so the picture stays readable."""
    by_id = {m.id: m for m in manifests}
    reach: dict[str, set[str]] = {}

    def reachable(node: str) -> set[str]:
        if node not in reach:
            reach[node] = set()
            for nxt in by_id[node].data["requires"]:
                if nxt in by_id:
                    reach[node] |= {nxt} | reachable(nxt)
        return reach[node]

    lines = ["```mermaid", "flowchart BT"]
    for layer in sorted({m.layer for m in manifests}):
        lines.append(f'  subgraph L{layer}["{LAYER_NAMES.get(layer, f"L{layer}")}"]')
        for m in sorted((x for x in manifests if x.layer == layer), key=lambda x: x.id):
            lines.append(f'    {_node(m.id)}["{m.id}"]')
        lines.append("  end")
    for m in sorted(manifests, key=lambda x: (x.layer, x.id)):
        direct = [r for r in m.data["requires"] if r in by_id]
        for required in sorted(direct):
            implied = any(required in reachable(other) for other in direct if other != required)
            if not implied:
                lines.append(f"  {_node(m.id)} --> {_node(required)}")
    lines.append("```")
    return "\n".join(lines)


def _node(module_id: str) -> str:
    return module_id.replace("-", "_")


def replace_block(text: str, start: str, end: str, content: str, name: str) -> str:
    if start not in text or end not in text:
        raise ValueError(f"{name}: markers {start} / {end} not found")
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    return f"{before}{start}\n{content}\n{end}{after}"


def generate(root: pathlib.Path, check: bool) -> list[str]:
    manifests = load_manifests(root)
    targets = [
        (root / "README.md", CATALOGUE_START, CATALOGUE_END, catalogue_table(root, manifests)),
        (root / "docs" / "architecture.md", GRAPH_START, GRAPH_END, dependency_graph(manifests)),
    ]
    problems = []
    for path, start, end, content in targets:
        name = _rel(root, path)
        if not path.is_file():
            problems.append(f"{name}: file not found")
            continue
        current = path.read_text(encoding="utf-8")
        try:
            updated = replace_block(current, start, end, content, name)
        except ValueError as error:
            problems.append(str(error))
            continue
        if updated == current:
            continue
        if check:
            problems.append(f"{name}: generated block is out of date; run: python tools/manifests.py generate")
        else:
            path.write_text(updated, encoding="utf-8", newline="\n")
            print(f"updated {name}")
    return problems


# --------------------------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["validate", "generate"])
    parser.add_argument("--check", action="store_true", help="generate: fail instead of writing when out of date")
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.command == "validate":
        errors = validate(root)
        if errors:
            print(f"manifests: {len(errors)} problem(s)", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        print(f"manifests: OK ({len(load_manifests(root))} manifests)")
        return 0

    problems = generate(root, args.check)
    if problems:
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("generated docs: up to date" if args.check else "generated docs: written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
