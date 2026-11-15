"""Update the integration manifest and build the existing release ZIP."""

from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path

# A deliberately narrow SemVer subset: no build metadata or shell punctuation.
_MAX_TAG_LENGTH = 128
_VERSION = re.compile(
    r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z][0-9A-Za-z-]*(?:\.[0-9A-Za-z][0-9A-Za-z-]*)*))?"
)


def main() -> None:
    """Validate the event tag before updating and packaging the integration."""
    tag = os.environ.get("RELEASE_TAG", "")
    match = _VERSION.fullmatch(tag) if len(tag) <= _MAX_TAG_LENGTH else None
    if match is None or (
        match[4]
        and any(
            part.isdigit() and len(part) > 1 and part[0] == "0"
            for part in match[4].split(".")
        )
    ):
        # Never echo an untrusted tag (it could contain workflow log commands).
        message = "Invalid release tag; expected v?MAJOR.MINOR.PATCH[-prerelease]"
        raise SystemExit(message)
    version = tag.removeprefix("v")
    integration = (
        Path(os.environ["GITHUB_WORKSPACE"]) / "custom_components" / "handballnet"
    )
    manifest_path = integration / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = version
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    asset = integration / "handballnet.zip"
    with zipfile.ZipFile(asset, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(integration.rglob("*")):
            if source.is_file() and source != asset:
                archive.write(source, source.relative_to(integration).as_posix())


if __name__ == "__main__":
    main()
