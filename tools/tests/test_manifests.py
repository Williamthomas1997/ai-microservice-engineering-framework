"""Tests for tools/manifests.py. Run: python -m pytest tools -q (no Maven needed)."""
from __future__ import annotations

import pathlib
import sys
import textwrap

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import manifests  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
G = manifests.GROUP_ID


def _pom(artifact: str, deps: tuple[str, ...] = (), modules: tuple[str, ...] = ()) -> str:
    dep_xml = "".join(f"<dependency><groupId>{G}</groupId><artifactId>{d}</artifactId></dependency>" for d in deps)
    mod_xml = "".join(f"<module>{m}</module>" for m in modules)
    return textwrap.dedent(f"""\
        <project xmlns="http://maven.apache.org/POM/4.0.0">
          <modelVersion>4.0.0</modelVersion>
          <artifactId>{artifact}</artifactId>
          <modules>{mod_xml}</modules>
          <dependencies>{dep_xml}</dependencies>
        </project>
        """)


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _module_yaml(mid: str, kind: str, layer: int, package: str, artifacts: dict, requires=(), bans=()) -> str:
    lines = [
        f"id: {mid}",
        f"kind: {kind}",
        f"layer: {layer}",
        "description: test module",
        f"package: io.github.williamthomas1997.amef.{package}",
        *(["stacks: [reactive, servlet]"] if kind == "brick" else []),
        "artifacts: { " + ", ".join(f"{k}: {v}" for k, v in artifacts.items()) + " }",
        "provides: []",
        f"requires: [{', '.join(requires)}]",
        "infra: []",
        f"bans: [{', '.join(bans)}]",
        f"config-prefix: amef.{package}",
        "status: planned",
        "milestone: M1",
    ]
    return "\n".join(lines) + "\n"


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A minimal valid repository: contracts (L1), one brick (L3), one app (L5), qa."""
    _write(tmp_path / "foundation/contracts/module.yaml",
           _module_yaml("contracts", "foundation", 1, "contracts", {"main": "amef-contracts"}))
    _write(tmp_path / "foundation/contracts/pom.xml", _pom("amef-contracts"))

    brick_artifacts = {s: f"amef-redis-{s}" for s in ("core", "reactive", "servlet")}
    _write(tmp_path / "bricks/redis/brick.yaml",
           _module_yaml("redis", "brick", 3, "redis", brick_artifacts, requires=["contracts"],
                        bans=["spring-boot-starter-data-redis"]))
    _write(tmp_path / "bricks/redis/core/pom.xml", _pom("amef-redis-core", deps=("amef-contracts",)))
    _write(tmp_path / "bricks/redis/reactive/pom.xml", _pom("amef-redis-reactive", deps=("amef-redis-core",)))
    _write(tmp_path / "bricks/redis/servlet/pom.xml", _pom("amef-redis-servlet", deps=("amef-redis-core",)))

    _write(tmp_path / "apps/gateway/module.yaml",
           _module_yaml("gateway", "app", 5, "gateway", {"main": "amef-gateway"}, requires=["contracts", "redis"]))
    _write(tmp_path / "apps/gateway/pom.xml", _pom("amef-gateway", deps=("amef-redis-reactive",)))

    _write(tmp_path / "qa/module.yaml", _module_yaml("qa", "qa", 5, "qa", {"main": "amef-qa"}))
    _write(tmp_path / "qa/pom.xml", _pom("amef-qa"))

    _write(tmp_path / "pom.xml", _pom("amef-root", modules=(
        "foundation/contracts", "bricks/redis/core", "bricks/redis/reactive", "bricks/redis/servlet",
        "apps/gateway")))
    _write(tmp_path / "build-parent/pom.xml", textwrap.dedent(f"""\
        <project>
          {manifests.BANS_START}
          <exclude>org.springframework.boot:spring-boot-starter-data-redis</exclude>
          {manifests.BANS_END}
        </project>
        """))
    libraries = ("amef-contracts", "amef-redis-core", "amef-redis-reactive", "amef-redis-servlet")
    managed = "".join(f"<dependency><groupId>{G}</groupId><artifactId>{a}</artifactId></dependency>"
                      for a in libraries)
    _write(tmp_path / "bom/pom.xml", '<project xmlns="http://maven.apache.org/POM/4.0.0"><artifactId>amef-bom'
                                     f'</artifactId><dependencyManagement><dependencies>{managed}'
                                     '</dependencies></dependencyManagement></project>')
    _write(tmp_path / "platform/rules/pom.xml", _pom("amef-platform-rules", deps=(*libraries, "amef-gateway")))
    _write(tmp_path / "bricks/redis/README.md", "# Redis brick\n")
    _write(tmp_path / "README.md", f"# t\n{manifests.CATALOGUE_START}\n{manifests.CATALOGUE_END}\n")
    _write(tmp_path / "docs/architecture.md", f"# a\n{manifests.GRAPH_START}\n{manifests.GRAPH_END}\n")
    return tmp_path


def _replace(path: pathlib.Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_valid_repository_passes(repo):
    assert manifests.validate(repo) == []


def test_upward_requirement_is_rejected(repo):
    _replace(repo / "foundation/contracts/module.yaml", "requires: []", "requires: [redis]")
    errors = manifests.validate(repo)
    assert any("same or a lower layer" in e for e in errors), errors


def test_cycle_is_rejected(repo):
    _write(repo / "bricks/messaging/brick.yaml", _module_yaml(
        "messaging", "brick", 3, "messaging", {s: f"amef-messaging-{s}" for s in ("core", "reactive", "servlet")},
        requires=["redis"]))
    for stack in ("core", "reactive", "servlet"):
        _write(repo / f"bricks/messaging/{stack}/pom.xml", _pom(f"amef-messaging-{stack}"))
        _replace(repo / "pom.xml", "<module>apps/gateway</module>",
                 f"<module>apps/gateway</module><module>bricks/messaging/{stack}</module>")
    _replace(repo / "bricks/redis/brick.yaml", "requires: [contracts]", "requires: [contracts, messaging]")
    errors = manifests.validate(repo)
    assert any(e.startswith("dependency cycle") for e in errors), errors


def test_unknown_requirement_is_rejected(repo):
    _replace(repo / "apps/gateway/module.yaml", "requires: [contracts, redis]", "requires: [contracts, nope]")
    assert any("unknown module 'nope'" in e for e in manifests.validate(repo))


def test_missing_artifact_module_is_rejected(repo):
    (repo / "bricks/redis/servlet/pom.xml").unlink()
    assert any("'amef-redis-servlet' has no pom.xml" in e for e in manifests.validate(repo))


def test_module_missing_from_reactor_is_rejected(repo):
    _replace(repo / "pom.xml", "<module>apps/gateway</module>", "")
    assert any("missing from the root pom.xml" in e for e in manifests.validate(repo))


def test_qa_in_reactor_is_rejected(repo):
    _replace(repo / "pom.xml", "<module>apps/gateway</module>", "<module>apps/gateway</module><module>qa</module>")
    assert any("must not be listed" in e for e in manifests.validate(repo))


def test_undeclared_pom_dependency_is_rejected(repo):
    _replace(repo / "apps/gateway/module.yaml", "requires: [contracts, redis]", "requires: [contracts]")
    errors = manifests.validate(repo)
    assert any("not in requires of 'gateway'" in e for e in errors), errors


def test_ban_not_enforced_is_rejected(repo):
    _replace(repo / "build-parent/pom.xml",
             "<exclude>org.springframework.boot:spring-boot-starter-data-redis</exclude>", "")
    assert any("is not enforced" in e for e in manifests.validate(repo))


def test_brick_with_wrong_stacks_is_rejected(repo):
    _replace(repo / "bricks/redis/brick.yaml", "stacks: [reactive, servlet]", "stacks: [reactive]")
    assert any("stacks" in e for e in manifests.validate(repo))


def test_generate_writes_blocks_and_check_detects_drift(repo):
    assert manifests.generate(repo, check=True)  # empty blocks are out of date
    assert manifests.generate(repo, check=False) == []
    assert manifests.generate(repo, check=True) == []

    readme = (repo / "README.md").read_text(encoding="utf-8")
    assert "| L3 | [`redis`](bricks/redis/) | brick |" in readme
    graph = (repo / "docs/architecture.md").read_text(encoding="utf-8")
    assert "flowchart BT" in graph
    assert "gateway --> redis" in graph
    assert "gateway --> contracts" not in graph  # implied through redis, removed by the transitive reduction

    _replace(repo / "bricks/redis/brick.yaml", "status: planned", "status: done")
    assert manifests.generate(repo, check=True)


def test_this_repository_is_valid_and_generated_blocks_are_current():
    assert manifests.validate(REPO_ROOT) == []
    assert manifests.generate(REPO_ROOT, check=True) == []


def test_library_artifact_missing_from_bom_is_rejected(repo):
    _replace(repo / "bom/pom.xml", "<artifactId>amef-redis-servlet</artifactId>", "<artifactId>other</artifactId>")
    assert any("not managed in bom/pom.xml" in e for e in manifests.validate(repo))


def test_module_missing_from_platform_rules_is_rejected(repo):
    _replace(repo / "platform/rules/pom.xml", "<artifactId>amef-gateway</artifactId>", "<artifactId>x</artifactId>")
    assert any("missing from platform/rules/pom.xml" in e for e in manifests.validate(repo))


def test_brick_without_readme_is_rejected(repo):
    (repo / "bricks/redis/README.md").unlink()
    assert any("brick has no README.md" in e for e in manifests.validate(repo))
