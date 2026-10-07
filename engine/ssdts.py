"""ACPI SSDT catalog for the Studio add/exclude picker."""

from __future__ import annotations

import base64
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from .paths import data_dir, mutable_file, work_dir

DATA_DIR = data_dir()
SSDTS_FILE = mutable_file("ssdts.json")
USER_SSDT_DIRNAME = "user-ssdts"
SKIP_ACPI_ADD = {"dsdt.aml", "dsdt.bin", "dynamicssdt.aml"}
OEM_SSDT_NAME = re.compile(r"^ssdt-\d+.*\.(aml|bin)$", re.I)


def _read_ssdts_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ssdts = data.get("ssdts", []) if isinstance(data, dict) else data
    return [s for s in ssdts if isinstance(s, dict) and (s.get("id") or s.get("path") or s.get("name"))]


def user_ssdt_dir() -> Path:
    path = work_dir() / USER_SSDT_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_ssdt_path(name: str) -> Path | None:
    safe = _safe_table_name(name)
    if not safe:
        return None
    path = user_ssdt_dir() / safe
    return path if path.exists() and path.stat().st_size > 32 else None


def list_user_ssdts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(user_ssdt_dir().iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in (".aml", ".bin"):
            continue
        data = path.read_bytes()[:8]
        kind = _acpi_signature(data)
        rows.append({
            "name": path.name,
            "path": path.name,
            "size": path.stat().st_size,
            "kind": kind,
            "injectSafe": _inject_safe(path.name, kind),
        })
    return rows


def load_ssdt_catalog() -> list[dict[str, Any]]:
    bundled = _read_ssdts_file(DATA_DIR / "ssdts.json")
    local = _read_ssdts_file(SSDTS_FILE)
    by_path: dict[str, dict[str, Any]] = {}
    for item in bundled + local:
        path = str(item.get("path") or item.get("name") or "")
        if path:
            by_path[path.lower()] = dict(item)
    for row in list_user_ssdts():
        key = row["name"].lower()
        existing = by_path.get(key)
        if existing:
            existing["userOverride"] = True
            existing["source"] = f"Your file ({row['name']})"
            existing["kind"] = row.get("kind") or existing.get("kind")
            existing["injectSafe"] = row.get("injectSafe", True)
            existing["skipInject"] = not existing["injectSafe"]
            if existing["skipInject"]:
                existing["when"] = "Stored for comparison only — OpenCore must not inject DSDT or OEM SSDT-N dumps."
        else:
            skip = not row.get("injectSafe", True)
            by_path[key] = {
                "id": Path(row["name"]).stem,
                "name": row["name"],
                "path": row["name"],
                "category": "custom" if not skip else "dump",
                "source": f"Your file ({row['name']})",
                "description": (
                    "Firmware ACPI dump (DSDT, HPET, APIC, OEM SSDT-0, …). Kept for SSDTTime / comparison — not added to ACPI → Add."
                    if skip else
                    "Loaded from a local .aml / ACPI zip. Overrides any T5810 or Dortania download of the same name."
                ),
                "when": (
                    "Clover/OpenCore origin dump. Use as input to SSDTTime; do not inject these tables."
                    if skip else
                    "Use for machine-specific SSDTTime output (T7910 dual-socket, SSDT-PCI1/PCIA, etc.)"
                ),
                "userOverride": True,
                "kind": row.get("kind"),
                "injectSafe": not skip,
                "skipInject": skip,
            }
    for item in by_path.values():
        item.setdefault("injectSafe", True)
        item.setdefault("skipInject", not item.get("injectSafe", True))
        item.setdefault("userOverride", False)
    return list(by_path.values())


def _ssdt_path(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("path") or item.get("name") or item.get("Path") or "").strip()
    return ""


def profile_ssdt_paths(profile: dict[str, Any] | None) -> list[str]:
    raw = (profile or {}).get("mandatorySsdt") or (profile or {}).get("recommendedSsdt") or []
    paths: list[str] = []
    seen: set[str] = set()
    for item in raw:
        path = _ssdt_path(item)
        key = path.lower()
        if path and key not in seen:
            paths.append(path)
            seen.add(key)
    return paths


def catalog_comment_for(path: str) -> str:
    key = path.lower()
    for item in load_ssdt_catalog():
        if str(item.get("path") or item.get("name") or "").lower() == key:
            return str(item.get("description") or path)
    return f"SSDT {path}"


def _safe_table_name(name: str) -> str:
    base = Path(str(name or "")).name
    if not base or base.startswith(".") or base.startswith("._"):
        return ""
    if "/" in base or "\\" in base:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.(aml|bin|AML|BIN|zip|ZIP)", base):
        return ""
    return base


def _acpi_signature(data: bytes) -> str:
    if len(data) < 4:
        return ""
    sig = data[:4].decode("ascii", errors="ignore").strip("\x00").upper()
    return sig if re.fullmatch(r"[A-Z0-9]{3,4}", sig) else ""


def _inject_safe(name: str, kind: str) -> bool:
    """OpenCore ACPI → Add is for SSDT hotpatches only — never firmware origin tables."""
    lower = name.lower()
    if lower in SKIP_ACPI_ADD or kind == "DSDT":
        return False
    if kind and kind != "SSDT":
        return False
    if OEM_SSDT_NAME.match(lower):
        return False
    stem = Path(lower).stem
    if not stem.startswith("ssdt"):
        return False
    return True


def _save_aml(name: str, data: bytes) -> dict[str, Any]:
    safe = _safe_table_name(name)
    if not safe or Path(safe).suffix.lower() not in (".aml", ".bin"):
        return {"ok": False, "name": name, "error": "Not an .aml/.bin table name."}
    if len(data) < 36:
        return {"ok": False, "name": safe, "error": "File is too small to be an ACPI table."}
    kind = _acpi_signature(data)
    dest = user_ssdt_dir() / safe
    dest.write_bytes(data)
    return {
        "ok": True,
        "name": safe,
        "kind": kind or "ACPI",
        "size": len(data),
        "injectSafe": _inject_safe(safe, kind),
        "userOverride": True,
    }


def ingest_user_acpi_files(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Save uploaded .aml/.bin tables or unzip an ACPI dump / SSDTTime results folder."""
    saved: list[dict[str, Any]] = []
    skipped: list[str] = []
    enable: list[str] = []
    for item in files or []:
        name = str((item or {}).get("name") or "")
        raw = (item or {}).get("b64") or (item or {}).get("base64") or ""
        if not raw:
            skipped.append(f"{name}: empty")
            continue
        try:
            data = base64.b64decode(raw)
        except Exception:
            skipped.append(f"{name}: not base64")
            continue
        suffix = Path(name).suffix.lower()
        if suffix == ".zip":
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    for info in zf.infolist():
                        if info.is_dir() or info.filename.startswith("__MACOSX"):
                            continue
                        inner = Path(info.filename).name
                        if inner.startswith("._"):
                            continue
                        if Path(inner).suffix.lower() not in (".aml", ".bin"):
                            continue
                        result = _save_aml(inner, zf.read(info.filename))
                        if result.get("ok"):
                            saved.append(result)
                            if result.get("injectSafe"):
                                enable.append(result["name"])
                        else:
                            skipped.append(f"{inner}: {result.get('error')}")
            except zipfile.BadZipFile:
                skipped.append(f"{name}: not a zip")
            continue
        result = _save_aml(name, data)
        if result.get("ok"):
            saved.append(result)
            if result.get("injectSafe"):
                enable.append(result["name"])
        else:
            skipped.append(f"{name}: {result.get('error')}")
    return {
        "success": True,
        "saved": saved,
        "skipped": skipped,
        "enable": enable,
        "userSsdts": list_user_ssdts(),
        "ssdts": load_ssdt_catalog(),
    }


def ingest_pending_acpi() -> dict[str, Any]:
    """Pick up files the native open-panel copied into Application Support/pending-acpi."""
    root = work_dir() / "pending-acpi"
    files: list[dict[str, Any]] = []
    if root.exists():
        for path in sorted(root.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            files.append({
                "name": path.name,
                "b64": base64.b64encode(path.read_bytes()).decode("ascii"),
            })
            try:
                path.unlink()
            except OSError:
                pass
    if not files:
        return {"success": False, "error": "No pending ACPI files."}
    return ingest_user_acpi_files(files)


def remove_user_ssdt(name: str) -> dict[str, Any]:
    path = user_ssdt_path(name)
    if not path:
        return {"success": False, "error": f"No uploaded table named {name}."}
    try:
        path.unlink()
    except OSError as exc:
        return {"success": False, "error": str(exc)}
    return {"success": True, "removed": path.name, "userSsdts": list_user_ssdts(), "ssdts": load_ssdt_catalog()}
