import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import pytest

from release_gate.checks import check


PATHS = {"readme": "README.md", "changelog": "CHANGELOG.md", "license": "LICENSE", "junit": "artifacts/junit.xml"}


@pytest.fixture
def project(tmp_path):
    configure(tmp_path, PATHS["changelog"])
    for item in ("readme", "license", "junit"):
        target = tmp_path / PATHS[item]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    return tmp_path


def configure(project, path, item="changelog"):
    paths = PATHS | {item: path}
    (project / "release-gate.toml").write_text(
        "schema_version = 1\n[checklist]\n" + "".join(
            f"{key} = {json.dumps(value)}\n" for key, value in paths.items()
        ), encoding="utf-8"
    )


def run_cli(project, *args):
    return subprocess.run(
        [str(Path(sys.executable).parent / "release-gate"), *args], cwd=project, capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize("content,code,exit_code", [
    ("# Changes\n- First release", "changelog_valid", 0),
    ("", "changelog_empty", 1),
    (" \n\t", "changelog_empty", 1),
])
def test_changelog_content(project, content, code, exit_code):
    (project / "CHANGELOG.md").write_text(content, encoding="utf-8")
    result = check(project)
    assert result.exit_code == exit_code
    assert result.checks[1]["code"] == code


def test_missing_changelog(project):
    result = check(project)
    assert result.exit_code == 1
    assert result.checks[1]["code"] == "changelog_missing"


@pytest.mark.parametrize("item", PATHS)
@pytest.mark.parametrize("kind", ["absolute", "parent", "symlink", "directory_symlink"])
def test_reject_escape_before_read(project, kind, item):
    outside = project.parent / f"{project.name}-outside"
    outside.mkdir()
    target = outside / "secret.md"
    target.write_text("outside", encoding="utf-8")
    if kind == "absolute":
        configured = str(target)
    elif kind == "parent":
        configured = f"../{outside.name}/secret.md"
    elif kind == "symlink":
        (project / "link.md").symlink_to(target)
        configured = "link.md"
    else:
        (project / "link").symlink_to(outside, target_is_directory=True)
        configured = "link/secret.md"
    configure(project, configured, item)
    with patch.object(Path, "read_text", side_effect=AssertionError("must not read")):
        result = check(project)
    assert result.exit_code == 2
    assert result.errors[0]["code"] == f"{item}_path_invalid"


@pytest.mark.parametrize("configured", ["docs/changes.md", "docs/../docs/changes.md", "link.md"])
def test_internal_paths(project, configured):
    (project / "docs").mkdir()
    target = project / "docs/changes.md"
    target.write_text("Changes", encoding="utf-8")
    (project / "link.md").symlink_to(target)
    configure(project, configured)
    assert check(project).exit_code == 0


@pytest.mark.parametrize("config", [
    "[broken", "schema_version = 2\n[changelog]\npath = 'x'",
    "schema_version = true\n[changelog]\npath = 'x'",
    "schema_version = 1\n[changelog]\npath = ''",
    "schema_version = 1\n[changelog]\npath = 1",
    "schema_version = 1\n[changelog]\npath = 'x'\nextra = true",
    "schema_version = 1", "",
])
def test_invalid_config(project, config):
    (project / "release-gate.toml").write_text(config, encoding="utf-8")
    result = check(project)
    assert result.exit_code == 2
    assert result.errors[0]["code"] == "config_invalid"


def test_missing_config(tmp_path):
    assert check(tmp_path).errors[0]["code"] == "config_missing"


@pytest.mark.parametrize("kind", ["directory", "invalid_utf8", "permission"])
def test_read_errors(project, kind):
    target = project / "CHANGELOG.md"
    if kind == "directory":
        target.mkdir()
    elif kind == "invalid_utf8":
        target.write_bytes(b"\xff")
    else:
        target.write_text("Changes", encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=PermissionError):
            result = check(project)
        assert result.exit_code == 2
        assert result.errors[0]["code"] == "changelog_read_error"
        return
    result = check(project)
    assert result.exit_code == 2
    assert result.errors[0]["code"] == "changelog_read_error"


def test_config_permission_error(project):
    with patch.object(Path, "open", side_effect=PermissionError):
        result = check(project)
    assert result.exit_code == 2
    assert result.errors[0]["code"] == "config_read_error"


@pytest.mark.parametrize("state,expected", [("valid", 0), ("missing", 1), ("empty", 1), ("invalid", 2)])
def test_cli_formats(project, state, expected):
    if state in {"valid", "empty"}:
        (project / "CHANGELOG.md").write_text("Changes" if state == "valid" else "")
    if state == "invalid":
        (project / "release-gate.toml").write_text("[broken")
    plain = run_cli(project, "check")
    structured = run_cli(project, "check", "--json")
    assert plain.returncode == structured.returncode == expected
    data = json.loads(structured.stdout)
    assert set(data) == {"schema_version", "status", "checks", "errors"}
    assert data["schema_version"] == 1
    assert data["status"] == {0: "passed", 1: "failed", 2: "error"}[expected]
    assert structured.stderr == ""
    assert structured.stdout.endswith("\n")
    if expected == 2:
        assert plain.stdout == ""
        assert "ERROR config_invalid:" in plain.stderr
    else:
        assert plain.stderr == ""
        assert ("APROVADO" if expected == 0 else "REPROVADO") in plain.stdout
        assert set(data["checks"][0]) == {"id", "status", "code", "path", "message"}


@pytest.mark.parametrize("args,expected", [(["--help"], 0), (["check", "--help"], 0), ([], 2), (["unknown"], 2), (["check", "--bad"], 2)])
def test_cli_arguments(project, args, expected):
    assert run_cli(project, *args).returncode == expected


@pytest.mark.parametrize("example,expected", [("with-changelog", 0), ("without-changelog", 1)])
@pytest.mark.parametrize("json_output", [False, True])
def test_examples(tmp_path, example, expected, json_output):
    source = Path(__file__).resolve().parents[1] / "examples" / example
    project = tmp_path / example
    shutil.copytree(source, project)
    result = run_cli(project, "check", *(["--json"] if json_output else []))
    assert result.returncode == expected
    assert result.stderr == ""
    if json_output:
        assert json.loads(result.stdout)["checks"][1]["code"] == (
            "changelog_valid" if expected == 0 else "changelog_missing"
        )


def test_config_invalid_utf8(project):
    (project / "release-gate.toml").write_bytes(b"\xff")
    result = check(project)
    assert result.exit_code == 2
    assert result.errors[0]["code"] == "config_invalid"


@pytest.mark.parametrize("json_output", [False, True])
def test_all_missing_reported_together(tmp_path, json_output):
    configure(tmp_path, "CHANGELOG.md")
    result = run_cli(tmp_path, "check", *(["--json"] if json_output else []))
    assert result.returncode == 1
    assert result.stderr == ""
    if json_output:
        data = json.loads(result.stdout)
        assert data["status"] == "failed"
        assert data["errors"] == []
        assert {entry["code"] for entry in data["checks"]} == {f"{item}_missing" for item in PATHS}
        assert {entry["path"] for entry in data["checks"]} == set(PATHS.values())
    else:
        for item, path in PATHS.items():
            assert f"FAIL {item}: {path} não encontrado." in result.stdout
        assert "Release gate: REPROVADO" in result.stdout


@pytest.mark.parametrize("item", ["readme", "license", "junit"])
def test_regular_files_only(project, item):
    (project / "CHANGELOG.md").write_text("Changes")
    target = project / PATHS[item]
    target.unlink()
    target.mkdir()
    result = check(project)
    assert result.exit_code == 1
    entry = next(entry for entry in result.checks if entry["id"] == item)
    assert entry["code"] == f"{item}_not_regular"


def test_junit_does_not_determine_test_success(project):
    (project / "CHANGELOG.md").write_text("Changes")
    (project / PATHS["junit"]).write_text('<testsuite tests="1" failures="1"/>')
    assert check(project).exit_code == 0
    (project / PATHS["junit"]).write_bytes(b"not XML\xff")
    assert check(project).exit_code == 0


@pytest.mark.parametrize("json_output", [False, True])
def test_errors_do_not_hide_missing_items(project, json_output):
    configure(project, "../outside.md", "readme")
    (project / "LICENSE").unlink()
    result = run_cli(project, "check", *(["--json"] if json_output else []))
    assert result.returncode == 2
    if json_output:
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert len(data["checks"]) == 4
        assert {entry["code"] for entry in data["checks"]} == {
            "readme_path_invalid", "changelog_missing", "license_missing", "junit_valid"
        }
        assert data["errors"][0]["id"] == "readme"
        assert result.stderr == ""
    else:
        assert "FAIL changelog:" in result.stdout
        assert "FAIL license:" in result.stdout
        assert "ERROR readme_path_invalid:" in result.stderr


@pytest.mark.parametrize("change", ["missing", "unknown", "empty", "type", "schema"])
def test_checklist_config_validation(project, change):
    config = (project / "release-gate.toml").read_text()
    if change == "missing":
        config = config.replace('license = "LICENSE"\n', '')
    elif change == "unknown":
        config += 'other = "file"\n'
    elif change == "empty":
        config = config.replace('"LICENSE"', '" "')
    elif change == "type":
        config = config.replace('"LICENSE"', 'false')
    else:
        config = config.replace('schema_version = 1', 'schema_version = 2')
    (project / "release-gate.toml").write_text(config)
    assert check(project).errors[0]["code"] == "config_invalid"


def test_examples_differ_only_by_changelog():
    examples = Path(__file__).resolve().parents[1] / "examples"
    def files(folder):
        return {str(path.relative_to(folder)): path.read_bytes()
                for path in folder.rglob("*") if path.is_file()}
    valid = files(examples / "with-changelog")
    missing = files(examples / "without-changelog")
    assert set(valid) - set(missing) == {"CHANGELOG.md"}
    valid.pop("CHANGELOG.md")
    assert valid == missing


def test_changelog_fifo_rejected_without_open(project):
    import os
    os.mkfifo(project / "CHANGELOG.md")
    with patch.object(Path, "read_text", side_effect=AssertionError("must not read")):
        assert check(project).errors[0]["code"] == "changelog_read_error"


@pytest.mark.parametrize("item", PATHS)
def test_internal_symlinks_for_every_item(project, item):
    (project / "CHANGELOG.md").write_text("Changes")
    (project / "linked-file").symlink_to(project / PATHS[item])
    configure(project, "linked-file", item)
    assert check(project).exit_code == 0


@pytest.mark.parametrize("item", PATHS)
def test_stat_permission_errors_are_aggregated(project, item):
    from release_gate.config import resolve_item
    target = resolve_item(project, PATHS[item], item)
    original_stat = Path.stat
    def guarded_stat(path, *args, **kwargs):
        if path == target:
            raise PermissionError("denied")
        return original_stat(path, *args, **kwargs)
    with patch.object(Path, "stat", guarded_stat):
        result = check(project)
    assert result.exit_code == 2
    assert len(result.checks) == 4
    assert result.errors[0]["code"] == f"{item}_read_error"
