"""Assemble a bootable OpenCore EFI folder (minus macOS).

Downloads the matching OpenCorePkg RELEASE zip, selected kexts, and compiled
SSDTs, then writes EFI/BOOT + EFI/OC with the Studio config.plist.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .kext_manager import fetch_latest_release, load_kext_catalog
from .plist_builder import build_config_plist
from .paths import builds_dir, cache_dir
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
    "SSDT-EC-USBX.aml": ["SSDT-EC-USBX.aml", "SSDT-EC-USBX-DESKTOP.aml"],
    "SSDT-EC-USBX-DESKTOP.aml": ["SSDT-EC-USBX-DESKTOP.aml", "SSDT-EC-USBX.aml"],
    "SSDT-AWAC.aml": ["SSDT-AWAC.aml", "SSDT-AWAC-DISABLE.aml"],
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


def _install_ssdts(efi_acpi: Path, names: list[str]) -> tuple[list[str], list[str]]:
    efi_acpi.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    missing: list[str] = []
    for name in names:
        if not name:
            continue
        candidates = SSDT_ALIASES.get(name, [name])
        saved = False
        last_error = ""
        for candidate in candidates:
            url = f"{DORTANIA_AML}/{candidate}"
            cache = CACHE_DIR / "ssdts" / candidate
            try:
                _download_cached(url, cache, timeout=30)
                if cache.exists() and cache.stat().st_size > 32:
                    shutil.copy2(cache, efi_acpi / name)
                    installed.append(name if candidate == name else f"{name} ← {candidate}")
                    saved = True
                    break
            except Exception as exc:
                last_error = str(exc)
                continue
        if not saved:
            missing.append(f"{name}: {last_error or 'no compiled AML found'}")
    return installed, missing


def assemble_efi(options: dict[str, Any]) -> dict[str, Any]:
    """Build EFI/ from the current Studio plist options."""
    oc_tag = resolve_opencore_tag(options.get("opencoreTag"))
    pl, xml_str = build_config_plist(options)

    ssdt_names = [e.get("Path") for e in pl.get("ACPI", {}).get("Add", []) if e.get("Path")]
    kext_ids = options.get("selectedKextIds") or []

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

    config_path = oc_dir / "config.plist"
    config_path.write_text(xml_str, encoding="utf-8")

    try:
        resources_note = _copy_ocbinary_resources(oc_dir)
    except Exception as exc:
        resources_note = f"OcBinaryData skipped: {exc}"
    kexts_ok, kexts_miss = _install_kexts(oc_dir / "Kexts", kext_ids)
    ssdts_ok, ssdts_miss = _install_ssdts(oc_dir / "ACPI", ssdt_names)

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
