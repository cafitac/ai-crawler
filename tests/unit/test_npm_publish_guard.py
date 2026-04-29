"""Release guard tests for npm publish workflow."""

from pathlib import Path

import pytest

from ai_crawler.release.npm_publish import (
    expected_npm_tag,
    read_release_versions,
    validate_publish_request,
    validate_release_versions,
)


def test_expected_npm_tag_uses_package_version() -> None:
    assert expected_npm_tag("0.1.1") == "npm-v0.1.1"


def test_validate_publish_request_accepts_matching_push_tag() -> None:
    validate_publish_request(event_name="push", ref_name="npm-v0.1.1", package_version="0.1.1")


def test_validate_publish_request_rejects_mismatched_push_tag() -> None:
    with pytest.raises(ValueError, match="expected npm-v0.1.1"):
        validate_publish_request(
            event_name="push",
            ref_name="npm-v0.1.2",
            package_version="0.1.1",
        )


def test_validate_publish_request_skips_tag_check_for_manual_dispatch() -> None:
    validate_publish_request(
        event_name="workflow_dispatch",
        ref_name="main",
        package_version="0.1.1",
    )


def test_validate_release_versions_rejects_mismatch(tmp_path: Path) -> None:
    package_json = tmp_path / "package.json"
    pyproject = tmp_path / "pyproject.toml"
    init_py = tmp_path / "__init__.py"

    package_json.write_text('{"version": "0.1.1"}\n')
    pyproject.write_text('[project]\nversion = "0.1.2"\n')
    init_py.write_text('__version__ = "0.1.1"\n')

    versions = read_release_versions(
        package_json_path=package_json,
        pyproject_path=pyproject,
        init_path=init_py,
    )

    with pytest.raises(ValueError, match="Version mismatch"):
        validate_release_versions(versions)


def test_validate_release_versions_accepts_consistent_versions(tmp_path: Path) -> None:
    package_json = tmp_path / "package.json"
    pyproject = tmp_path / "pyproject.toml"
    init_py = tmp_path / "__init__.py"

    package_json.write_text('{"version": "0.1.1"}\n')
    pyproject.write_text('[project]\nversion = "0.1.1"\n')
    init_py.write_text('__version__ = "0.1.1"\n')

    versions = read_release_versions(
        package_json_path=package_json,
        pyproject_path=pyproject,
        init_path=init_py,
    )

    validate_release_versions(versions)
    assert versions.package == "0.1.1"
    assert versions.python_project == "0.1.1"
    assert versions.python_runtime == "0.1.1"
