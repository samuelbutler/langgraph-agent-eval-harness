from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SUSPICIOUS_JS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("child_process usage", re.compile(r"\b(require\(['\"]child_process['\"]\)|from ['\"]child_process['\"])")),
    ("dynamic eval", re.compile(r"\b(eval|Function)\s*\(")),
    ("shell download command", re.compile(r"\b(curl|wget)\s+https?://")),
    ("network socket usage", re.compile(r"\b(net|tls)\.connect\s*\(")),
    ("filesystem home access", re.compile(r"\b(process\.env\.HOME|os\.homedir\s*\()")),
    ("credential environment access", re.compile(r"process\.env\.(NPM_TOKEN|GITHUB_TOKEN|AWS_|SSH_|TOKEN|SECRET)")),
)

SUSPICIOUS_PY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("subprocess usage", re.compile(r"\b(subprocess|os\.system|pty\.spawn)\b")),
    ("dynamic code execution", re.compile(r"\b(eval|exec)\s*\(")),
    ("network usage", re.compile(r"\b(socket|urllib\.request|requests)\b")),
)

LIFECYCLE_SCRIPTS = {
    "preinstall",
    "install",
    "postinstall",
    "prepublish",
    "prepublishOnly",
    "prepare",
}

TEXT_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".json",
    ".sh",
    ".bash",
    ".py",
    ".node",
}

MAX_FILE_BYTES = 1_000_000
MAX_EXTRACTED_FILES = 10_000
MAX_EXTRACTED_BYTES = 100_000_000


@dataclass(frozen=True)
class Finding:
    severity: str
    kind: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class PackageSnapshot:
    package: str
    version: str
    source: str
    sha256: str
    root: Path
    package_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NpmScanResult:
    package: str
    from_version: str
    to_version: str
    verdict: str
    findings: list[Finding]
    added_files: list[str]
    removed_files: list[str]
    changed_files: list[str]
    isolated_workdir: str


def scan_npm_update(
    package: str,
    from_version: str,
    to_version: str,
    *,
    registry_url: str = "https://registry.npmjs.org",
    keep_workdir: bool = False,
) -> NpmScanResult:
    """Download and inspect an npm package update in an isolated temp directory.

    The function never executes package code or lifecycle scripts. Tarballs are downloaded
    into a temporary directory, extracted with path traversal protection, inspected, then
    deleted unless `keep_workdir=True`.
    """
    workdir_obj = tempfile.TemporaryDirectory(prefix="lageh-npm-scan-")
    workdir = Path(workdir_obj.name)
    try:
        old = _download_snapshot(package, from_version, registry_url, workdir / "old")
        new = _download_snapshot(package, to_version, registry_url, workdir / "new")
        result = _compare_snapshots(old, new, keep_workdir_path=str(workdir))
        return result
    finally:
        if keep_workdir:
            workdir_obj._finalizer.detach()  # type: ignore[attr-defined]
        else:
            workdir_obj.cleanup()


def scan_npm_tarball_update(
    package: str,
    from_version: str,
    to_version: str,
    old_tarball: Path,
    new_tarball: Path,
    *,
    keep_workdir: bool = False,
) -> NpmScanResult:
    """Inspect two local npm tarballs using the same isolated extraction path."""
    workdir_obj = tempfile.TemporaryDirectory(prefix="lageh-npm-scan-")
    workdir = Path(workdir_obj.name)
    try:
        old = _snapshot_from_tarball(package, from_version, old_tarball, workdir / "old")
        new = _snapshot_from_tarball(package, to_version, new_tarball, workdir / "new")
        result = _compare_snapshots(old, new, keep_workdir_path=str(workdir))
        return result
    finally:
        if keep_workdir:
            workdir_obj._finalizer.detach()  # type: ignore[attr-defined]
        else:
            workdir_obj.cleanup()


def _download_snapshot(package: str, version: str, registry_url: str, dest: Path) -> PackageSnapshot:
    metadata_url = f"{registry_url.rstrip('/')}/{urllib.parse.quote(package, safe='@')}"
    with urllib.request.urlopen(metadata_url, timeout=30) as response:
        metadata = json.loads(response.read().decode("utf-8"))
    try:
        tarball_url = metadata["versions"][version]["dist"]["tarball"]
    except KeyError as exc:
        raise ValueError(f"No npm tarball found for {package}@{version}") from exc
    tarball = dest.with_suffix(".tgz")
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(tarball_url, tarball)  # noqa: S310 - explicit user-requested scanner
    return _snapshot_from_tarball(package, version, tarball, dest)


def _snapshot_from_tarball(package: str, version: str, tarball: Path, dest: Path) -> PackageSnapshot:
    dest.mkdir(parents=True, exist_ok=True)
    sha256 = hashlib.sha256(tarball.read_bytes()).hexdigest()
    _safe_extract_tarball(tarball, dest)
    root = _find_package_root(dest)
    package_json_path = root / "package.json"
    package_json: dict[str, Any] = {}
    if package_json_path.exists():
        package_json = json.loads(package_json_path.read_text(encoding="utf-8"))
    return PackageSnapshot(package, version, str(tarball), sha256, root, package_json)


def _safe_extract_tarball(tarball: Path, dest: Path) -> None:
    total_size = 0
    file_count = 0
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            target = (dest / member.name).resolve()
            if not str(target).startswith(str(dest.resolve()) + '/') and target != dest.resolve():
                raise ValueError(f"Unsafe tarball path: {member.name}")
            if member.issym() or member.islnk():
                raise ValueError(f"Refusing link in tarball: {member.name}")
            if member.isfile():
                file_count += 1
                total_size += member.size
                if file_count > MAX_EXTRACTED_FILES:
                    raise ValueError("Tarball contains too many files")
                if total_size > MAX_EXTRACTED_BYTES:
                    raise ValueError("Tarball is too large after extraction")
        archive.extractall(dest, filter="data")


def _find_package_root(dest: Path) -> Path:
    package_dir = dest / "package"
    if package_dir.exists():
        return package_dir
    return dest


def _compare_snapshots(old: PackageSnapshot, new: PackageSnapshot, *, keep_workdir_path: str) -> NpmScanResult:
    old_files = _file_hashes(old.root)
    new_files = _file_hashes(new.root)
    added = sorted(new_files.keys() - old_files.keys())
    removed = sorted(old_files.keys() - new_files.keys())
    changed = sorted(path for path in new_files.keys() & old_files.keys() if new_files[path] != old_files[path])

    findings: list[Finding] = []
    findings.extend(_scan_package_json(old.package_json, new.package_json))
    for rel_path in added + changed:
        findings.extend(_scan_file(new.root / rel_path, rel_path))

    verdict = "safe" if not any(f.severity == "high" for f in findings) else "suspicious"
    return NpmScanResult(
        package=new.package,
        from_version=old.version,
        to_version=new.version,
        verdict=verdict,
        findings=findings,
        added_files=added,
        removed_files=removed,
        changed_files=changed,
        isolated_workdir=keep_workdir_path,
    )


def _file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _scan_package_json(old: dict[str, Any], new: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    old_scripts = old.get("scripts", {}) if isinstance(old.get("scripts", {}), dict) else {}
    new_scripts = new.get("scripts", {}) if isinstance(new.get("scripts", {}), dict) else {}
    for script in sorted(LIFECYCLE_SCRIPTS & set(new_scripts)):
        if old_scripts.get(script) != new_scripts.get(script):
            findings.append(
                Finding(
                    severity="high",
                    kind="lifecycle-script",
                    message=f"new or changed lifecycle script: {script}={new_scripts[script]!r}",
                    path="package.json",
                )
            )
    if old.get("name") and new.get("name") and old.get("name") != new.get("name"):
        findings.append(Finding("high", "metadata-change", "package name changed", "package.json"))
    return findings


def _scan_file(path: Path, rel_path: str) -> list[Finding]:
    if path.stat().st_size > MAX_FILE_BYTES or path.suffix not in TEXT_EXTENSIONS:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    findings: list[Finding] = []
    patterns = SUSPICIOUS_PY_PATTERNS if path.suffix == ".py" else SUSPICIOUS_JS_PATTERNS
    for kind, pattern in patterns:
        if pattern.search(text):
            findings.append(Finding("high", kind, f"suspicious pattern found: {kind}", rel_path))
    if _looks_like_encoded_payload(text):
        findings.append(Finding("medium", "encoded-payload", "large base64-like payload found", rel_path))
    return findings


def _looks_like_encoded_payload(text: str) -> bool:
    candidates = re.findall(r"[A-Za-z0-9+/]{160,}={0,2}", text)
    for candidate in candidates:
        try:
            decoded = base64.b64decode(candidate, validate=True)
        except Exception:
            continue
        if len(decoded) > 100:
            return True
    return False


def cleanup_scan_workdir(path: str) -> None:
    """Remove an isolated scan directory returned with keep_workdir=True."""
    shutil.rmtree(path, ignore_errors=True)
