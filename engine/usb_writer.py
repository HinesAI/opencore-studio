"""Copy a built OpenCore EFI folder onto a USB volume (macOS diskutil)."""

from __future__ import annotations

import plistlib
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .efi_builder import last_manifest

INTERNAL_NAME_HINTS = ("macintosh", "macos", "data", "system", "untitled")


def _run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, capture_output=True, check=False)


def _diskutil_plist(args: list[str]) -> dict[str, Any]:
    proc = _run(["diskutil"] + args + ["-plist"])
    if proc.returncode != 0 or not proc.stdout:
        return {}
    try:
        data = plistlib.loads(proc.stdout)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _is_internal_volume(name: str, mount: str) -> bool:
    lowered = f"{name} {mount}".lower()
    if mount in ("/", "/System/Volumes/Data", "/System/Volumes/Update"):
        return True
    return any(hint in lowered for hint in ("macintosh hd", "macos", "/system/volumes"))


def list_usb_targets() -> dict[str, Any]:
    """Mounted volumes that can receive an EFI folder, plus whole external disks."""
    volumes: list[dict[str, Any]] = []
    volumes_root = Path("/Volumes")
    if volumes_root.exists():
        for item in sorted(volumes_root.iterdir()):
            if not item.is_dir() or item.name.startswith("."):
                continue
            if _is_internal_volume(item.name, str(item)):
                continue
            info = _diskutil_plist(["info", str(item)])
            if not info or not info.get("DeviceIdentifier"):
                continue
            if info.get("Internal"):
                continue
            protocol = str(info.get("BusProtocol") or "").lower()
            removable = bool(info.get("Ejectable")) or protocol in ("usb", "secure digital", "thunderbolt")
            if not removable:
                continue
            volumes.append({
                "kind": "volume",
                "name": item.name,
                "mountPoint": str(item),
                "device": info.get("DeviceIdentifier") or "",
                "fileSystem": info.get("FilesystemType") or info.get("FilesystemName") or "",
                "size": info.get("TotalSize") or 0,
                "ejectable": bool(info.get("Ejectable")),
                "writable": True,
            })

    disks: list[dict[str, Any]] = []
    listing = _diskutil_plist(["list", "external"])
    for disk in listing.get("AllDisksAndPartitions") or []:
        ident = disk.get("DeviceIdentifier")
        if not ident or "s" in ident[4:]:
            continue
        info = _diskutil_plist(["info", ident])
        if info.get("Internal"):
            continue
        disks.append({
            "kind": "disk",
            "name": info.get("MediaName") or ident,
            "device": ident,
            "size": info.get("TotalSize") or disk.get("Size") or 0,
            "ejectable": bool(info.get("Ejectable")),
            "protocol": info.get("BusProtocol") or "",
        })

    return {"success": True, "volumes": volumes, "disks": disks}


def copy_efi_to_volume(mount_point: str) -> dict[str, Any]:
    manifest = last_manifest()
    if not manifest.get("success"):
        return {"success": False, "error": "Build an EFI folder first."}
    efi_src = Path(manifest["efiPath"])
    if not efi_src.exists():
        return {"success": False, "error": "Built EFI folder is missing. Rebuild it."}

    dest_root = Path(mount_point)
    if not dest_root.exists() or not dest_root.is_dir():
        return {"success": False, "error": f"Volume '{mount_point}' is not mounted."}
    if _is_internal_volume(dest_root.name, str(dest_root)):
        return {"success": False, "error": "Refusing to write to an internal system volume."}

    dest_efi = dest_root / "EFI"
    if dest_efi.exists():
        shutil.rmtree(dest_efi)
    shutil.copytree(efi_src, dest_efi)
    bootx = dest_efi / "BOOT" / "BOOTx64.efi"
    oc = dest_efi / "OC" / "OpenCore.efi"
    cfg = dest_efi / "OC" / "config.plist"
    return {
        "success": bootx.exists() and oc.exists() and cfg.exists(),
        "destination": str(dest_efi),
        "bootx64": bootx.exists(),
        "opencore": oc.exists(),
        "config": cfg.exists(),
        "message": f"Copied EFI to {dest_efi}. Set firmware to boot from this USB (UEFI).",
    }


def prepare_usb_and_copy(device: str, confirm: str) -> dict[str, Any]:
    """Erase an external disk as FAT32/GPT named OPENCORE, then copy EFI."""
    if str(confirm or "").strip() != "ERASE":
        return {"success": False, "error": "Pass confirm='ERASE' to wipe the selected external disk."}
    ident = str(device or "").strip().lstrip("/dev/")
    if not ident.startswith("disk") or "s" in ident[4:]:
        return {"success": False, "error": "Select a whole disk (diskN), not a partition (diskNsM)."}
    info = _diskutil_plist(["info", ident])
    if not info:
        return {"success": False, "error": f"diskutil could not inspect {ident}."}
    if info.get("Internal"):
        return {"success": False, "error": "Refusing to erase an internal disk."}
    if not info.get("Ejectable") and str(info.get("BusProtocol") or "").lower() not in ("usb", "secure digital", "thunderbolt"):
        return {"success": False, "error": f"{ident} does not look like removable USB storage."}

    proc = _run(["diskutil", "eraseDisk", "FAT32", "OPENCORE", "GPT", ident])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace")
        return {"success": False, "error": f"diskutil eraseDisk failed: {err.strip()}"}

    mount = Path("/Volumes/OPENCORE")
    if not mount.exists():
        return {"success": False, "error": "Disk was erased but /Volumes/OPENCORE did not appear."}
    copied = copy_efi_to_volume(str(mount))
    copied["erased"] = ident
    copied["volume"] = str(mount)
    return copied
