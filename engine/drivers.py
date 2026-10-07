"""UEFI driver catalog for the Studio add/exclude picker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import data_dir, mutable_file

DATA_DIR = data_dir()
DRIVERS_FILE = mutable_file("drivers.json")


def _read_drivers_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    drivers = data.get("drivers", []) if isinstance(data, dict) else data
    return [d for d in drivers if isinstance(d, dict) and (d.get("id") or d.get("path"))]


def load_driver_catalog() -> list[dict[str, Any]]:
    bundled = _read_drivers_file(DATA_DIR / "drivers.json")
    local = _read_drivers_file(DRIVERS_FILE)
    by_id = {str(d.get("id") or d.get("path")): d for d in bundled}
    by_id.update({str(d.get("id") or d.get("path")): d for d in local})
    return list(by_id.values())


def default_driver_paths(profile: dict[str, Any] | None = None) -> list[str]:
    catalog = load_driver_catalog()
    paths = [str(d.get("path")) for d in catalog if d.get("defaultEnabled") and d.get("path")]
    extras = (profile or {}).get("uefiDrivers") or (profile or {}).get("recommendedDrivers") or []
    seen = {p.lower() for p in paths}
    for item in extras:
        path = item if isinstance(item, str) else str((item or {}).get("Path") or (item or {}).get("name") or "")
        path = path.strip()
        if path and path.lower() not in seen:
            paths.append(path)
            seen.add(path.lower())
    if not any(p.lower() == "openruntime.efi" for p in paths):
        paths.insert(0, "OpenRuntime.efi")
    return paths
