"""ACPI binary patches (HPET _CRS→XCRS and SSDTTime IRQ companions)."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from .paths import data_dir, mutable_file

DATA_DIR = data_dir()
PATCHES_FILE = mutable_file("acpi_patches.json")


def _read_patches_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    patches = data.get("patches", []) if isinstance(data, dict) else data
    return [p for p in patches if isinstance(p, dict) and p.get("id")]


def load_acpi_patch_catalog() -> list[dict[str, Any]]:
    bundled = _read_patches_file(DATA_DIR / "acpi_patches.json")
    local = _read_patches_file(PATCHES_FILE)
    by_id = {str(p["id"]): p for p in bundled}
    by_id.update({str(p["id"]): p for p in local})
    return list(by_id.values())


def companion_patch_ids_for_ssdts(ssdt_names: list[str]) -> list[str]:
    wanted = {str(n).strip().lower() for n in ssdt_names if n}
    ids: list[str] = []
    for patch in load_acpi_patch_catalog():
        req = str(patch.get("requiresSsdt") or "").strip().lower()
        if req and req in wanted:
            ids.append(str(patch["id"]))
    return ids


def resolve_acpi_patch_ids(
    options: dict[str, Any],
    profile: dict[str, Any] | None,
    ssdt_names: list[str],
) -> list[str]:
    catalog = {str(p["id"]): p for p in load_acpi_patch_catalog()}
    ssdt_set = {str(n).strip().lower() for n in ssdt_names if n}
    selected = options.get("selectedAcpiPatches")
    if isinstance(selected, list):
        ids = [str(i) for i in selected if str(i) in catalog]
    else:
        ids = [str(i) for i in ((profile or {}).get("acpiPatches") or []) if str(i) in catalog]
        for pid in companion_patch_ids_for_ssdts(ssdt_names):
            if pid not in ids:
                ids.append(pid)
    kept: list[str] = []
    seen: set[str] = set()
    for pid in ids:
        if pid in seen:
            continue
        patch = catalog.get(pid)
        if not patch:
            continue
        req = str(patch.get("requiresSsdt") or "").strip().lower()
        if req and req not in ssdt_set:
            continue
        seen.add(pid)
        kept.append(pid)
    return kept


def _hex_bytes(value: Any) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    text = re.sub(r"(?i)0x", "", str(value or ""))
    text = re.sub(r"[^0-9A-Fa-f]", "", text)
    if len(text) % 2:
        text = "0" + text
    try:
        return bytes.fromhex(text)
    except ValueError:
        return b""


def build_acpi_patch_entries(base_pl: dict[str, Any], patch_ids: list[str]) -> list[dict[str, Any]]:
    catalog = {str(p["id"]): p for p in load_acpi_patch_catalog()}
    sample = ((base_pl.get("ACPI") or {}).get("Patch") or [])
    template = next((p for p in sample if isinstance(p, dict)), {}) or {}
    entries: list[dict[str, Any]] = []
    for pid in patch_ids:
        spec = catalog.get(pid)
        if not spec:
            continue
        entry = copy.deepcopy(template) if template else {}
        entry.update({
            "Base": str(spec.get("base") or ""),
            "BaseSkip": 0,
            "Comment": str(spec.get("comment") or pid),
            "Count": int(spec.get("count") or 0),
            "Enabled": True,
            "Find": _hex_bytes(spec.get("findHex")),
            "Limit": 0,
            "Mask": b"",
            "OemTableId": b"",
            "Replace": _hex_bytes(spec.get("replaceHex")),
            "ReplaceMask": b"",
            "Skip": 0,
            "TableLength": 0,
            "TableSignature": b"",
        })
        entries.append(entry)
    return entries
