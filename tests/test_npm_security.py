from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from langgraph_agent_eval_harness.npm_security import (
    cleanup_scan_workdir,
    scan_npm_tarball_update,
)


def make_npm_tarball(tmp_path: Path, name: str, version: str, files: dict[str, str]) -> Path:
    package_dir = tmp_path / f"{name}-{version}" / "package"
    package_dir.mkdir(parents=True)
    for rel_path, content in files.items():
        path = package_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    tarball = tmp_path / f"{name}-{version}.tgz"
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(package_dir, arcname="package")
    return tarball


def test_npm_scanner_flags_new_lifecycle_script_and_child_process(tmp_path: Path):
    old = make_npm_tarball(
        tmp_path,
        "demo",
        "1.0.0",
        {
            "package.json": json.dumps({"name": "demo", "version": "1.0.0"}),
            "index.js": "module.exports = () => 'ok';\n",
        },
    )
    new = make_npm_tarball(
        tmp_path,
        "demo",
        "1.0.1",
        {
            "package.json": json.dumps(
                {"name": "demo", "version": "1.0.1", "scripts": {"postinstall": "node post.js"}}
            ),
            "index.js": "require('child_process').execSync('whoami');\n",
            "post.js": "console.log('install');\n",
        },
    )

    result = scan_npm_tarball_update("demo", "1.0.0", "1.0.1", old, new)

    assert result.verdict == "suspicious"
    assert "index.js" in result.changed_files
    assert any(f.kind == "lifecycle-script" for f in result.findings)
    assert any(f.kind == "child_process usage" for f in result.findings)


def test_npm_scanner_keeps_code_isolated_when_requested(tmp_path: Path):
    old = make_npm_tarball(
        tmp_path,
        "demo",
        "1.0.0",
        {"package.json": json.dumps({"name": "demo", "version": "1.0.0"})},
    )
    new = make_npm_tarball(
        tmp_path,
        "demo",
        "1.0.1",
        {"package.json": json.dumps({"name": "demo", "version": "1.0.1"})},
    )

    result = scan_npm_tarball_update("demo", "1.0.0", "1.0.1", old, new, keep_workdir=True)

    isolated = Path(result.isolated_workdir)
    try:
        assert isolated.exists()
        assert isolated.name.startswith("lageh-npm-scan-")
        assert (isolated / "old" / "package" / "package.json").exists()
        assert (isolated / "new" / "package" / "package.json").exists()
    finally:
        cleanup_scan_workdir(result.isolated_workdir)


def test_npm_scanner_rejects_path_traversal_tarball(tmp_path: Path):
    tarball = tmp_path / "evil.tgz"
    payload = tmp_path / "payload.txt"
    payload.write_text("bad", encoding="utf-8")
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(payload, arcname="package/../../evil.txt")

    with pytest.raises(ValueError, match="Unsafe tarball path"):
        scan_npm_tarball_update("evil", "1.0.0", "1.0.1", tarball, tarball)
