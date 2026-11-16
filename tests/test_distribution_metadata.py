"""Distribution metadata regressions for the custom-repository route."""

import json
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "handballnet"


def test_release_manifest_version_matches_first_changelog_entry():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    version = manifest["version"]
    assert version.count(".") == 2 and all(part.isdigit() for part in version.split(".")), "Release manifest must use MAJOR.MINOR.PATCH without a dev suffix"
    assert (ROOT / "CHANGELOG.md").read_text().splitlines()[2].startswith(f"## {version} –")


def test_core_aiohttp_is_not_redeclared_in_custom_manifest():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    requirements = {Requirement(item).name.lower() for item in manifest.get("requirements", [])}
    assert "aiohttp" not in requirements, "HA supplies aiohttp; hassfest rejects its redeclaration"


def test_custom_source_does_not_require_a_release_asset():
    config = json.loads((ROOT / "hacs.json").read_text())
    assert config["zip_release"] is False
    assert config["homeassistant"] == "2026.11.0"


def test_integration_archive_contains_all_three_bundled_card_modules():
    for name in ("handball-team-card.js", "handball-tournament-table-card.js", "handball-schedule-card.js"):
        assert (COMPONENT / "www" / name).is_file()
