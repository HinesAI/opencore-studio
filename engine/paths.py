"""Resolve bundled vs writable Studio paths.

Read-only catalogs stay next to the code. Cache, EFI builds, and backups go
to Application Support when the UI is running from OpenCore Studio.app.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BUNDLE_DATA = ROOT_DIR / "data"


def _running_from_app() -> bool:
    return ".app/Contents/Resources" in str(ROOT_DIR)


def work_dir() -> Path:
    override = (os.environ.get("OCS_WORK_DIR") or "").strip()
    if override:
        path = Path(override).expanduser()
    elif _running_from_app():
        path = Path.home() / "Library" / "Application Support" / "OpenCore Studio"
    else:
        path = BUNDLE_DATA
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    return BUNDLE_DATA


def cache_dir() -> Path:
    path = work_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def builds_dir() -> Path:
    path = work_dir() / "builds" / "latest"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir() -> Path:
    path = work_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def uses_portable_store() -> bool:
    return _running_from_app() or bool((os.environ.get("OCS_WORK_DIR") or "").strip())


def mutable_file(name: str) -> Path:
    """Writable copy of a bundled data file (Sample, kexts.json, …)."""
    bundled = BUNDLE_DATA / name
    dest = work_dir() / name
    if dest.resolve() == bundled.resolve():
        return bundled
    if not dest.exists() and bundled.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, dest)
    return dest if dest.exists() else bundled


def first_run_path() -> Path:
    return work_dir() / "first-run.json"
