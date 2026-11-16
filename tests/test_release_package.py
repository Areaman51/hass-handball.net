"""Exercise release packaging with real manifests, subprocesses and ZIPs."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_package.py"


@pytest.fixture
def release_tree(tmp_path):
    workspace = tmp_path / "checkout with spaces"
    integration = workspace / "custom_components" / "handballnet"
    (integration / "www").mkdir(parents=True)
    manifest = {
        "domain": "handballnet",
        "version": "0.0.31",
        "name": "Handball – Grüße",
        "description": 'Keep \'"version": "0.0.31"\' as text',
        "dependencies": ["file_upload"],
    }
    (integration / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    (integration / "__init__.py").write_text("# integration\n", encoding="utf-8")
    (integration / "www" / "card.js").write_bytes(b"// card\n")
    return workspace, integration, manifest


def run_release(workspace, tag):
    env = {**os.environ, "GITHUB_WORKSPACE": str(workspace)}
    if tag is None:
        env.pop("RELEASE_TAG", None)
    else:
        env["RELEASE_TAG"] = tag
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=workspace.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "tag",
    ["1.2.3", "v1.2.3", "0.0.0", "v12.34.56-rc.1", "1.2.3-beta-2", "1.2.3-alpha.0"],
)
def test_cli_updates_only_json_version_and_builds_original_asset(release_tree, tag):
    workspace, integration, original = release_tree
    result = run_release(workspace, tag)
    assert result.returncode == 0, result.stderr
    expected = {**original, "version": tag.removeprefix("v")}
    assert json.loads((integration / "manifest.json").read_text("utf-8")) == expected
    asset = integration / "handballnet.zip"
    with zipfile.ZipFile(asset) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {
            "manifest.json",
            "__init__.py",
            "www/card.js",
        }
        assert json.loads(archive.read("manifest.json")) == expected
        assert archive.read("www/card.js") == b"// card\n"
        assert archive.read("__init__.py") == b"# integration\n"


@pytest.mark.parametrize(
    "tag",
    [
        None,
        "",
        "v",
        "1.2",
        "1.2.3.4",
        "vv1.2.3",
        "V1.2.3",
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "1.2.3-01",
        "1.2.3-rc.01",
        "1.2.3-",
        "1.2.3--",
        "1.2.3-rc.-1",
        "1.2.3-rc..1",
        "1.2.3+build.1",
        "1.2.3\n",
        "1.2.3\r\n",
        " 1.2.3",
        "1.2.3 ",
        "１.2.3",
        "1.2.3-ä",
        "../../1.2.3",
        "1.2.3;touch PWNED",
        "v1.2.3$(touch PWNED)",
        "v1.2.3`touch PWNED`",
        'v1.2.3"; touch PWNED; #',
        "1.2.3' && touch PWNED #",
        "1.2.3\ntouch PWNED",
        "1.2.3|touch PWNED",
        "1.2.3> PWNED",
        "${{ secrets.GITHUB_TOKEN }}",
        "1.2.3-" + "a" * 200,
    ],
)
def test_rejects_invalid_tags_before_any_file_changes(release_tree, tag):
    workspace, integration, _ = release_tree
    before = (integration / "manifest.json").read_bytes()
    result = run_release(workspace, tag)
    assert result.returncode != 0
    assert "Invalid release tag" in result.stderr
    assert (integration / "manifest.json").read_bytes() == before
    assert not (integration / "handballnet.zip").exists()
    assert not (workspace.parent / "PWNED").exists()
    assert not (workspace / "PWNED").exists()


@pytest.mark.parametrize(
    "name", ["publish.yaml", "hacs_validate.yaml", "hassfest.yaml"]
)
def test_workflows_use_verified_pins_and_do_not_persist_checkout_credentials(name):
    text = (SCRIPT.parents[1] / ".github" / "workflows" / name).read_text("utf-8")
    # Official GitHub REST refs resolved and commit objects verified 2026-11-15.
    pins = {
        "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python": "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
        "hacs/action": "1ebf01c408f29afcb6406bd431bc98fd8cbb15aa",
        "home-assistant/actions/hassfest": "86d4564712fa02543c808e3a693dd04f9d3f8361",
        "softprops/action-gh-release": "3d0d9888cb7fd7b750713d6e236d1fcb99157228",
    }
    uses = re.findall(r"uses:\s*[\"']?([^\s\"']+)", text)
    assert uses
    for action in uses:
        repository, ref = action.split("@")
        assert pins[repository] == ref
    if any(action.startswith("actions/checkout@") for action in uses):
        assert "persist-credentials: false" in text
    assert "permissions:" in text
    assert "contents: read" in text


@pytest.mark.parametrize(
    "tag", ["v2.3.4-rc.1", 'v1.2.3"; touch PWNED; #', "v1.2.3$(touch PWNED)"]
)
def test_publish_passes_tag_only_as_env_and_runs_helper(release_tree, tag):
    workspace, integration, original = release_tree
    text = (SCRIPT.parents[1] / ".github" / "workflows" / "publish.yaml").read_text(
        "utf-8"
    )
    assert "RELEASE_TAG: ${{ github.event.release.tag_name }}" in text
    # One literal shell command, no workflow expressions interpolated into code.
    commands = re.findall(r"(?m)^        run: (.+)$", text)
    assert commands == ['python "$GITHUB_WORKSPACE/scripts/release_package.py"']
    assert "sed " not in text
    assert (
        'files: "${{ github.workspace }}/custom_components/handballnet/handballnet.zip"'
        in text
    )
    # Exercise the exact shell command from the workflow with a real helper copy.
    (workspace / "scripts").mkdir()
    (workspace / "scripts" / SCRIPT.name).write_bytes(SCRIPT.read_bytes())
    env = {
        **os.environ,
        "PATH": str(Path(sys.executable).parent)
        + os.pathsep
        + os.environ.get("PATH", ""),
        "GITHUB_WORKSPACE": str(workspace),
        "RELEASE_TAG": tag,
    }
    before = (integration / "manifest.json").read_bytes()
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-euo", "pipefail", "-c", commands[0]],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if tag != "v2.3.4-rc.1":
        assert result.returncode != 0
        assert "Invalid release tag" in result.stderr
        assert (integration / "manifest.json").read_bytes() == before
        assert not (integration / "handballnet.zip").exists()
        assert not (workspace / "PWNED").exists()
        return
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(integration / "handballnet.zip") as archive:
        assert json.loads(archive.read("manifest.json")) == {
            **original,
            "version": "2.3.4-rc.1",
        }


def test_repeated_packaging_replaces_asset_without_including_itself(release_tree):
    workspace, integration, _ = release_tree
    for tag in ["v1.2.3", "v1.2.4"]:
        result = run_release(workspace, tag)
        assert result.returncode == 0, result.stderr
        with zipfile.ZipFile(integration / "handballnet.zip") as archive:
            assert archive.testzip() is None
            assert "handballnet.zip" not in archive.namelist()
            assert json.loads(archive.read("manifest.json"))["version"] == tag[1:]


def test_malformed_manifest_is_not_overwritten_and_no_archive_created(release_tree):
    workspace, integration, _ = release_tree
    malformed = b'{"version": invalid JSON}'
    (integration / "manifest.json").write_bytes(malformed)
    result = run_release(workspace, "v1.2.3")
    assert result.returncode != 0
    assert (integration / "manifest.json").read_bytes() == malformed
    assert not (integration / "handballnet.zip").exists()
