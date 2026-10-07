"""Assemble a bootable OpenCore EFI folder (minus macOS).

Downloads the matching OpenCorePkg RELEASE zip, selected kexts, and compiled
SSDTs, then writes EFI/BOOT + EFI/OC with the Studio config.plist.
"""

from __future__ import annotations

import json
import plistlib
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .kext_manager import fetch_latest_release, load_kext_catalog
from .plist_builder import build_config_plist, kext_ids_for_build
from .paths import builds_dir, cache_dir, data_dir
from .profiles import get_profile
from .ssdts import OEM_SSDT_NAME, SKIP_ACPI_ADD, user_ssdt_path
from .updater import fetch_opencore_releases, load_state

CACHE_DIR = cache_dir()
BUILD_DIR = builds_dir()
MANIFEST_PATH = BUILD_DIR / "manifest.json"
USER_AGENT = "OpenCoreStudio-EFI/1.0"

DORTANIA_AML = "https://raw.githubusercontent.com/dortania/Getting-Started-With-ACPI/master/extra-files/compiled"
OCBINARY_ZIP = "https://github.com/acidanthera/OcBinaryData/archive/refs/heads/master.zip"

SSDT_ALIASES = {
    "SSDT-PLUG.aml": ["SSDT-PLUG.aml", "SSDT-PLUG-DRTNIA.aml"],
    "SSDT-PLUG-ALT.aml": ["SSDT-PLUG-ALT.aml", "SSDT-PLUG.aml", "SSDT-PLUG-DRTNIA.aml"],
    "SSDT-EC.aml": ["SSDT-EC.aml", "SSDT-EC-DESKTOP.aml"],
    "SSDT-EC-LAPTOP.aml": ["SSDT-EC-LAPTOP.aml"],
    "SSDT-EC-USBX.aml": ["SSDT-EC-USBX.aml", "SSDT-EC-USBX-DESKTOP.aml"],
    "SSDT-EC-USBX-LAPTOP.aml": ["SSDT-EC-USBX-LAPTOP.aml"],
    "SSDT-EC-USBX-DESKTOP.aml": ["SSDT-EC-USBX-DESKTOP.aml", "SSDT-EC-USBX.aml"],
    "SSDT-AWAC.aml": ["SSDT-AWAC.aml", "SSDT-AWAC-DISABLE.aml"],
    "SSDT-RTC0-RANGE.aml": ["SSDT-RTC0-RANGE-HEDT.aml", "SSDT-RTC0-RANGE.aml"],
    "SSDT-UNC.aml": ["SSDT-UNC.aml"],
    "SSDT-HPET.aml": ["SSDT-HPET.aml"],
    "SSDT-SBUS-MCHC.aml": ["SSDT-SBUS-MCHC.aml"],
    "SSDT-X99-USBX.aml": ["SSDT-X99-USBX.aml"],
}

SSDT_EXTRA_URLS = {
    "SSDT-HPET.aml": [
        "https://raw.githubusercontent.com/BillDH2k/Hackintosh-DELL-T5810-OpenCore/main/EFI/OC/ACPI/SSDT-HPET.aml",
    ],
    "SSDT-SBUS-MCHC.aml": [
        "https://raw.githubusercontent.com/BillDH2k/Hackintosh-DELL-T5810-OpenCore/main/EFI/OC/ACPI/SSDT-SBUS-MCHC.aml",
    ],
    "SSDT-X99-USBX.aml": [
        "https://raw.githubusercontent.com/BillDH2k/Hackintosh-DELL-T5810-OpenCore/main/EFI/OC/ACPI/SSDT-X99-USBX.aml",
        "https://raw.githubusercontent.com/bombons/x99-SSDT/master/SSDT-X99-USBX.aml",
        "https://raw.githubusercontent.com/KGP/X99-System-SSDTs/master/SSDT-X99-USBX.aml",
    ],
}

SKIP_KEXT_DOWNLOAD = {"UTBMap"}


def _http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _download_cached(url: str, dest: Path, timeout: int = 90) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.write_bytes(_http_get(url, timeout=timeout))
    return dest


def prefetch_opencore_release(tag: str | None = None) -> Path:
    oc_tag = resolve_opencore_tag(tag)
    oc_url = f"https://github.com/acidanthera/OpenCorePkg/releases/download/{oc_tag}/OpenCore-{oc_tag}-RELEASE.zip"
    return _download_cached(oc_url, CACHE_DIR / f"OpenCore-{oc_tag}-RELEASE.zip", timeout=180)


def resolve_opencore_tag(requested: str | None = None) -> str:
    tag = (requested or "").strip()
    if tag and tag not in ("latest", "bundled"):
        return tag
    state_tag = str(load_state().get("opencore", {}).get("tag") or "")
    if state_tag and state_tag not in ("bundled", "rolled-back"):
        return state_tag
    releases = fetch_opencore_releases(limit=1)
    if not releases:
        raise RuntimeError("Could not resolve an OpenCorePkg release tag.")
    return releases[0]["tag"]


def _extract_x64_efi(zip_path: Path, dest_efi: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        root = Path(tmp)
        matches = list(root.rglob("OpenCore.efi"))
        efi_src = None
        for match in matches:
            parts = [p.upper() for p in match.parts]
            if "X64" in parts or match.parent.name == "OC":
                # .../EFI/OC/OpenCore.efi → EFI
                efi_src = match.parent.parent
                if efi_src.name != "EFI":
                    continue
                break
        if efi_src is None and matches:
            efi_src = matches[0].parent.parent
        if efi_src is None or not efi_src.exists():
            raise RuntimeError("OpenCore zip did not contain EFI/OC/OpenCore.efi")
        if dest_efi.exists():
            shutil.rmtree(dest_efi)
        shutil.copytree(efi_src, dest_efi)


def _copy_ocbinary_resources(efi_oc: Path) -> str:
    zip_path = _download_cached(OCBINARY_ZIP, CACHE_DIR / "OcBinaryData-master.zip")
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        extracted = Path(tmp)
        resources = next(extracted.rglob("Resources"), None)
        if resources is None or not resources.is_dir():
            return "OcBinaryData had no Resources folder"
        dest = efi_oc / "Resources"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(resources, dest)
    return "OcBinaryData Resources installed"


def _find_kext_bundle(root: Path, bundle_path: str) -> Path | None:
    target = bundle_path.rstrip("/").split("/")[-1]
    hits = [p for p in root.rglob(target) if p.is_dir() and (p / "Contents" / "Info.plist").exists()]
    if not hits:
        return None
    hits.sort(key=lambda p: (0 if "DEBUG" not in p.name.upper() else 1, len(p.parts)))
    return hits[0]


def _install_kexts(efi_kexts: Path, selected_ids: list[str]) -> tuple[list[str], list[str]]:
    catalog = {k["id"]: k for k in load_kext_catalog()}
    installed: list[str] = []
    missing: list[str] = []
    efi_kexts.mkdir(parents=True, exist_ok=True)

    for kid in selected_ids:
        info = catalog.get(kid)
        if not info:
            missing.append(f"{kid}: not in catalog")
            continue
        if kid in SKIP_KEXT_DOWNLOAD:
            missing.append(f"{kid}: generated on-machine later (USB map)")
            continue
        repo = str(info.get("github") or "").strip()
        if not repo:
            missing.append(f"{kid}: no GitHub repo")
            continue
        release = fetch_latest_release(repo)
        if not release or release.get("error") or not release.get("downloadUrl"):
            missing.append(f"{kid}: no release zip ({(release or {}).get('error', 'none')})")
            continue
        asset = release.get("assetName") or f"{kid}.zip"
        zip_path = _download_cached(release["downloadUrl"], CACHE_DIR / "kexts" / f"{repo.replace('/', '_')}__{asset}")
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmp)
            bundle = _find_kext_bundle(Path(tmp), info.get("bundlePath") or f"{kid}.kext")
            if not bundle:
                missing.append(f"{kid}: zip had no {info.get('bundlePath')}")
                continue
            dest = efi_kexts / bundle.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(bundle, dest)
            installed.append(f"{kid} ({release.get('tag')})")
    return installed, missing


def _copy_if_aml(src: Path, dest: Path) -> bool:
    if src.exists() and src.stat().st_size > 32:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return True
    return False


def _extract_ssdt_from_oc_zip(oc_zip: Path | None, name: str, dest: Path) -> bool:
    if not oc_zip or not oc_zip.exists():
        return False
    cache = CACHE_DIR / "ssdts" / f"oczip-{name}"
    if _copy_if_aml(cache, dest):
        return True
    try:
        with zipfile.ZipFile(oc_zip) as zf:
            matches = [
                info.filename
                for info in zf.infolist()
                if info.filename.replace("\\", "/").endswith(name)
            ]
            if not matches:
                return False
            matches.sort(key=lambda p: (0 if "Binaries" in p else 1, len(p)))
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(zf.read(matches[0]))
            return _copy_if_aml(cache, dest)
    except Exception:
        return False


def _compile_ssdt_from_oc_zip(oc_zip: Path | None, name: str, dest: Path) -> bool:
    if not oc_zip or not oc_zip.exists() or not shutil.which("iasl"):
        return False
    dsl_name = name.replace(".aml", ".dsl")
    try:
        with zipfile.ZipFile(oc_zip) as zf, tempfile.TemporaryDirectory() as tmp:
            matches = [
                info.filename
                for info in zf.infolist()
                if info.filename.replace("\\", "/").endswith(dsl_name)
            ]
            if not matches:
                return False
            dsl_path = Path(tmp) / dsl_name
            dsl_path.write_bytes(zf.read(matches[0]))
            import subprocess
            compiled = Path(tmp) / name
            subprocess.run(
                ["iasl", "-p", str(compiled.with_suffix("")), str(dsl_path)],
                check=False,
                capture_output=True,
            )
            return _copy_if_aml(compiled, dest)
    except Exception:
        return False


def _install_ssdts(
    efi_acpi: Path,
    names: list[str],
    oc_zip: Path | None = None,
) -> tuple[list[str], list[str]]:
    efi_acpi.mkdir(parents=True, exist_ok=True)
    bundled = data_dir() / "ssdts"
    installed: list[str] = []
    missing: list[str] = []
    selected = {n.lower() for n in names if n}
    skip_x99_usbx = "ssdt-ec-usbx.aml" in selected
    for name in names:
        if not name:
            continue
        dest = efi_acpi / name
        saved = False
        last_error = ""
        if name.lower() in SKIP_ACPI_ADD or OEM_SSDT_NAME.match(name.lower()):
            continue
        if skip_x99_usbx and name.lower() == "ssdt-x99-usbx.aml":
            continue
        user = user_ssdt_path(name)
        if not user:
            for candidate in SSDT_ALIASES.get(name, []):
                user = user_ssdt_path(candidate)
                if user:
                    break
        if user and _copy_if_aml(user, dest):
            installed.append(f"{name} ← your file")
            saved = True
        if not saved and bundled.exists() and _copy_if_aml(bundled / name, dest):
            installed.append(f"{name} ← bundled")
            saved = True
        if not saved:
            candidates = SSDT_ALIASES.get(name, [name])
            for candidate in candidates:
                url = f"{DORTANIA_AML}/{candidate}"
                cache = CACHE_DIR / "ssdts" / candidate
                try:
                    _download_cached(url, cache, timeout=30)
                    if _copy_if_aml(cache, dest):
                        installed.append(name if candidate == name else f"{name} ← {candidate}")
                        saved = True
                        break
                except Exception as exc:
                    last_error = str(exc)
                    continue
        if not saved and _extract_ssdt_from_oc_zip(oc_zip, name, dest):
            installed.append(f"{name} ← OpenCorePkg zip")
            saved = True
        if not saved:
            for url in SSDT_EXTRA_URLS.get(name, []):
                cache = CACHE_DIR / "ssdts" / f"extra-{name}"
                try:
                    _download_cached(url, cache, timeout=30)
                    if _copy_if_aml(cache, dest):
                        installed.append(f"{name} ← extra")
                        saved = True
                        break
                except Exception as exc:
                    last_error = str(exc)
                    continue
        if not saved and _compile_ssdt_from_oc_zip(oc_zip, name, dest):
            installed.append(f"{name} ← compiled")
            saved = True
        if not saved:
            missing.append(f"{name}: {last_error or 'no compiled AML found'}")
    return installed, missing


def _drop_missing_ssdts(pl: dict[str, Any], missing: list[str]) -> list[str]:
    miss = {row.split(":", 1)[0].strip().lower() for row in missing}
    add = ((pl.get("ACPI") or {}).get("Add") or [])
    kept = []
    dropped = []
    for entry in add:
        path = str((entry or {}).get("Path") or "")
        if path.lower() in miss:
            dropped.append(path)
            continue
        kept.append(entry)
    if "ACPI" in pl:
        pl["ACPI"]["Add"] = kept
    return dropped


def _ensure_uefi_drivers(oc_dir: Path, driver_names: list[str]) -> tuple[list[str], list[str]]:
    """Make sure every enabled config.plist UEFI driver file exists under EFI/OC/Drivers.

    Tools-only OpenCore binaries (when present) are promoted into Drivers. Anything
    still missing is returned so assemble_efi can drop it from the plist — OpenCore
    HaltLevel treats a missing enabled driver as a boot-stopping error.
    """
    drivers_dir = oc_dir / "Drivers"
    tools_dir = oc_dir / "Tools"
    drivers_dir.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    missing: list[str] = []
    aliases = {
        "OpenHfsPlus.efi": ["OpenHfsPlus.efi", "HfsPlus.efi", "HfsPlusLegacy.efi"],
        "ResetTSCAdjust.efi": ["ResetTSCAdjust.efi"],
        "ResetNvramEntry.efi": ["ResetNvramEntry.efi"],
    }
    search_roots = [drivers_dir, tools_dir, oc_dir]
    zip_root = oc_dir.parent.parent
    if zip_root.exists():
        search_roots.append(zip_root)
    for name in driver_names:
        if not name:
            continue
        dest = drivers_dir / name
        if dest.exists() and dest.stat().st_size > 0:
            installed.append(name)
            continue
        found = None
        for candidate in aliases.get(name, [name]):
            for folder in search_roots:
                if not folder.exists():
                    continue
                hits = [p for p in folder.rglob(candidate) if p.is_file()]
                if hits:
                    found = hits[0]
                    break
            if found:
                break
        if not found:
            missing.append(name)
            continue
        if found.resolve() != dest.resolve():
            shutil.copy2(found, dest)
        installed.append(name if found.name == name else f"{name} ← {found.name}")
    return installed, missing


def _drop_missing_uefi_drivers(pl: dict[str, Any], missing_names: list[str]) -> list[str]:
    """Remove enabled UEFI drivers whose .efi files are not in the EFI folder."""
    if not missing_names:
        return []
    miss = {str(n).lower() for n in missing_names}
    drivers = ((pl.get("UEFI") or {}).get("Drivers") or [])
    kept = []
    dropped = []
    for entry in drivers:
        path = str((entry or {}).get("Path") or "")
        if path.lower() in miss:
            dropped.append(path)
            continue
        kept.append(entry)
    if "UEFI" in pl:
        pl["UEFI"]["Drivers"] = kept
    return dropped


def assemble_efi(options: dict[str, Any]) -> dict[str, Any]:
    """Build EFI/ from the current Studio plist options."""
    oc_tag = resolve_opencore_tag(options.get("opencoreTag"))
    profile = get_profile(str(options.get("profileId") or "")) or {}
    merged_options = dict(options)
    merged_options["selectedKextIds"] = kext_ids_for_build(options, profile)
    pl, xml_str = build_config_plist(merged_options)

    ssdt_names = [e.get("Path") for e in pl.get("ACPI", {}).get("Add", []) if e.get("Path")]
    kext_ids = merged_options["selectedKextIds"]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)

    oc_zip = prefetch_opencore_release(oc_tag)
    efi_root = BUILD_DIR / "EFI"
    _extract_x64_efi(oc_zip, efi_root)
    oc_dir = efi_root / "OC"
    oc_dir.mkdir(parents=True, exist_ok=True)
    (oc_dir / "ACPI").mkdir(exist_ok=True)
    (oc_dir / "Kexts").mkdir(exist_ok=True)
    (oc_dir / "Drivers").mkdir(exist_ok=True)
    (oc_dir / "Tools").mkdir(exist_ok=True)

    try:
        resources_note = _copy_ocbinary_resources(oc_dir)
    except Exception as exc:
        resources_note = f"OcBinaryData skipped: {exc}"
    kexts_ok, kexts_miss = _install_kexts(oc_dir / "Kexts", kext_ids)
    ssdts_ok, ssdts_miss = _install_ssdts(oc_dir / "ACPI", ssdt_names, oc_zip)
    dropped_ssdts = _drop_missing_ssdts(pl, ssdts_miss)
    driver_names = [
        str(d.get("Path") or "")
        for d in (pl.get("UEFI") or {}).get("Drivers") or []
        if d.get("Enabled", True) and d.get("Path")
    ]
    drivers_ok, drivers_miss = _ensure_uefi_drivers(oc_dir, driver_names)
    dropped = _drop_missing_uefi_drivers(pl, drivers_miss)
    if dropped or dropped_ssdts:
        xml_str = plistlib.dumps(pl, fmt=plistlib.FMT_XML, sort_keys=True).decode("utf-8")

    config_path = oc_dir / "config.plist"
    config_path.write_text(xml_str, encoding="utf-8")

    zip_path = BUILD_DIR / "OpenCore-Studio-EFI.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in efi_root.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(BUILD_DIR))

    manifest = {
        "builtAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "opencoreTag": oc_tag,
        "efiPath": str(efi_root),
        "zipPath": str(zip_path),
        "configPath": str(config_path),
        "kextsInstalled": kexts_ok,
        "kextsMissing": kexts_miss,
        "ssdtsInstalled": ssdts_ok,
        "ssdtsMissing": ssdts_miss,
        "ssdtsOmitted": dropped_ssdts,
        "driversInstalled": drivers_ok,
        "driversMissing": [],
        "driversOmitted": dropped,
        "resources": resources_note,
        "bootloader": {
            "BOOTx64": (efi_root / "BOOT" / "BOOTx64.efi").exists(),
            "OpenCore": (oc_dir / "OpenCore.efi").exists(),
        },
        "readyForUsb": (efi_root / "BOOT" / "BOOTx64.efi").exists() and (oc_dir / "OpenCore.efi").exists() and config_path.exists(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"success": True, **manifest}


def last_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"success": False, "error": "No EFI has been built yet."}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["success"] = True
    data["efiExists"] = Path(data.get("efiPath") or "").exists()
    data["zipExists"] = Path(data.get("zipPath") or "").exists()
    return data


def efi_zip_path() -> Path | None:
    manifest = last_manifest()
    if not manifest.get("success"):
        return None
    path = Path(manifest.get("zipPath") or "")
    return path if path.exists() else None
