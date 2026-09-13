"""Reload a generated (or hand-tuned) config.plist back into Studio state."""

from __future__ import annotations

import plistlib
from pathlib import Path
from typing import Any

from .hardware import list_gpus
from .kext_manager import load_kext_catalog
from .paths import work_dir
from .profiles import list_profiles


def _hex_bytes(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex().upper()
    return str(value or "")


def _kext_id_from_bundle(bundle_path: str, catalog: list[dict[str, Any]]) -> str | None:
    path = (bundle_path or "").rstrip("/").lower()
    name = path.split("/")[-1]
    for kext in catalog:
        bundle = str(kext.get("bundlePath", "")).lower()
        kid = str(kext.get("id", ""))
        if bundle and (bundle == path or path.endswith(bundle) or name == bundle.lower()):
            return kid
        if kid and name.startswith(kid.lower() + ".kext"):
            return kid
    if name.endswith(".kext"):
        return name[: -len(".kext")]
    return None


def _guess_profile(pl: dict[str, Any], kext_ids: list[str], boot_args: str) -> str | None:
    args = boot_args.lower()
    patches = pl.get("Kernel", {}).get("Patch", []) or []
    amd_patch = any("cpuid_cores_per_package" in str(p.get("Comment", "")).lower() for p in patches)
    emulate = pl.get("Kernel", {}).get("Emulate", {}) or {}
    quirks = pl.get("Kernel", {}).get("Quirks", {}) or {}
    model = str(pl.get("PlatformInfo", {}).get("Generic", {}).get("SystemProductName", ""))

    if amd_patch or emulate.get("DummyPowerManagement"):
        if "NootedRed" in kext_ids:
            return "amd_apu_nooted"
        return "amd_ryzen_zen3_4"
    if "CpuTopologyRebuild" in kext_ids or "-wegnoigpu" in args:
        return "intel_alder_raptor"
    if quirks.get("AppleXcpmExtraMsrs") and model in ("MacPro7,1", "iMacPro1,1"):
        return "intel_xeon_w_skylake"
    if model in ("iMac20,1", "iMac20,2"):
        return "intel_comet_lake"
    if model in ("iMac19,1", "iMac19,2"):
        return "intel_coffee_lake"
    if model in ("iMac18,1", "iMac18,2", "iMac18,3"):
        return "intel_kaby_lake"
    if model in ("iMac17,1",):
        return "intel_skylake"
    if model in ("iMac15,1", "iMac14,2"):
        return "intel_haswell"
    if model in ("MacPro7,1", "iMacPro1,1"):
        return "intel_xeon_w_skylake"
    ids = {p["id"] for p in list_profiles()}
    return "intel_comet_lake" if "intel_comet_lake" in ids else None


def _guess_gpu(kext_ids: list[str], boot_args: str) -> str | None:
    args = boot_args.lower()
    if "NootedRed" in kext_ids:
        return "amd_apu"
    if "NootRX" in kext_ids:
        return "amd_navi22"
    if "agdpmod=pikera" in args:
        return "amd_navi21"
    if "-wegnoigpu" in args:
        return "intel_uhd_7x0"
    if "nvda_drv" in args:
        return "nvidia_web"
    families = {g["id"]: g for g in list_gpus()}
    return "amd_polaris" if "amd_polaris" in families else None


def import_config_plist(xml_text: str) -> dict[str, Any]:
    raw = xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text
    try:
        pl = plistlib.loads(raw)
    except Exception as exc:
        return {"success": False, "error": f"Not a valid Apple XML plist: {exc}"}
    if not isinstance(pl, dict):
        return {"success": False, "error": "Plist root is not a dictionary."}

    catalog = load_kext_catalog()
    kext_ids = []
    for entry in pl.get("Kernel", {}).get("Add", []) or []:
        if not entry.get("Enabled", True):
            continue
        kid = _kext_id_from_bundle(str(entry.get("BundlePath", "")), catalog)
        if kid:
            kext_ids.append(kid)

    apple_guid = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
    nvram = ((pl.get("NVRAM") or {}).get("Add") or {}).get(apple_guid) or {}
    boot_args = str(nvram.get("boot-args") or "")

    generic = ((pl.get("PlatformInfo") or {}).get("Generic") or {})
    smbios = {
        "model": generic.get("SystemProductName") or "iMac20,1",
        "serial": generic.get("SystemSerialNumber") or "",
        "mlb": generic.get("MLB") or "",
        "uuid": generic.get("SystemUUID") or "",
        "rom": _hex_bytes(generic.get("ROM")),
    }

    studio = {
        "profileId": _guess_profile(pl, kext_ids, boot_args),
        "gpuId": _guess_gpu(kext_ids, boot_args),
        "selectedKextIds": kext_ids,
        "bootArgs": boot_args,
        "smbios": smbios,
        "quirks": {
            "ACPI": dict((pl.get("ACPI") or {}).get("Quirks") or {}),
            "Booter": dict((pl.get("Booter") or {}).get("Quirks") or {}),
            "Kernel": dict((pl.get("Kernel") or {}).get("Quirks") or {}),
            "UEFI": dict((pl.get("UEFI") or {}).get("Quirks") or {}),
        },
        "ssdts": [
            e.get("Path") for e in (pl.get("ACPI") or {}).get("Add") or [] if e.get("Enabled", True)
        ],
        "amdPatches": bool(pl.get("Kernel", {}).get("Patch")),
    }

    return {
        "success": True,
        "studio": studio,
        "xml": xml_text if isinstance(xml_text, str) else raw.decode("utf-8", errors="replace"),
    }


def import_config_bytes(raw: bytes) -> dict[str, Any]:
    try:
        parsed = plistlib.loads(raw)
        xml_text = plistlib.dumps(parsed, fmt=plistlib.FMT_XML).decode("utf-8")
    except Exception as exc:
        try:
            xml_text = raw.decode("utf-8")
        except Exception:
            return {"success": False, "error": f"Not a valid Apple plist: {exc}"}
    return import_config_plist(xml_text)


def pending_import_path() -> Path:
    return work_dir() / "pending-import.plist"


def import_pending_plist() -> dict[str, Any]:
    path = pending_import_path()
    if not path.exists():
        return {"success": False, "error": "No config.plist was chosen."}
    raw = path.read_bytes()
    try:
        path.unlink()
    except OSError:
        pass
    return import_config_bytes(raw)
