"""Validation helpers for npm publish workflow consistency."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PACKAGE_JSON = ROOT / "package.json"
DEFAULT_PYPROJECT = ROOT / "pyproject.toml"
DEFAULT_INIT = ROOT / "src" / "ai_crawler" / "__init__.py"

_VERSION_PATTERN = re.compile(r'^(?:version|__version__)\s*=\s*"([^"]+)"$', re.MULTILINE)


@dataclass(frozen=True)
class ReleaseVersions:
    package: str
    python_project: str
    python_runtime: str


def expected_npm_tag(package_version: str) -> str:
    return f"npm-v{package_version}"


def read_release_versions(
    package_json_path: Path = DEFAULT_PACKAGE_JSON,
    pyproject_path: Path = DEFAULT_PYPROJECT,
    init_path: Path = DEFAULT_INIT,
) -> ReleaseVersions:
    package_data = json.loads(package_json_path.read_text())
    pyproject_text = pyproject_path.read_text()
    init_text = init_path.read_text()
    return ReleaseVersions(
        package=package_data["version"],
        python_project=_extract_version(pyproject_text, source=str(pyproject_path)),
        python_runtime=_extract_version(init_text, source=str(init_path)),
    )


def validate_release_versions(versions: ReleaseVersions) -> None:
    unique_versions = {versions.package, versions.python_project, versions.python_runtime}
    if len(unique_versions) == 1:
        return
    msg = (
        "Version mismatch detected: "
        f"package.json={versions.package}, "
        f"pyproject.toml={versions.python_project}, "
        f"__init__.py={versions.python_runtime}"
    )
    raise ValueError(msg)


def validate_publish_request(event_name: str, ref_name: str, package_version: str) -> None:
    if event_name != "push":
        return
    expected_tag = expected_npm_tag(package_version)
    if ref_name == expected_tag:
        return
    raise ValueError(f"Publish tag mismatch: got {ref_name}, expected {expected_tag}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate npm publish release inputs.")
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--ref-name", required=True)
    parser.add_argument("--package-json", type=Path, default=DEFAULT_PACKAGE_JSON)
    parser.add_argument("--pyproject", type=Path, default=DEFAULT_PYPROJECT)
    parser.add_argument("--init-file", type=Path, default=DEFAULT_INIT)
    args = parser.parse_args()

    versions = read_release_versions(
        package_json_path=args.package_json,
        pyproject_path=args.pyproject,
        init_path=args.init_file,
    )
    validate_release_versions(versions)
    validate_publish_request(
        event_name=args.event_name,
        ref_name=args.ref_name,
        package_version=versions.package,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "package_version": versions.package,
                "expected_tag": expected_npm_tag(versions.package),
            }
        )
    )
    return 0


def _extract_version(text: str, *, source: str) -> str:
    match = _VERSION_PATTERN.search(text)
    if match is None:
        raise ValueError(f"Could not find version in {source}")
    return match.group(1)


if __name__ == "__main__":
    raise SystemExit(main())
