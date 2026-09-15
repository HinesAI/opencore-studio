"""Copy a built OpenCore EFI folder onto a USB volume (macOS diskutil)."""

from __future__ import annotations

import plistlib
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .efi_builder import last_manifest

SYSTEM_MOUNTS = (
    "/",
    "/System/Volumes/Data",
    "/System/Volumes/Update",
    "/System/Volumes/Preboot",
    "/System/Volumes/VM",
)
INTERNAL_VOLUME_NAMES = {
    "macintosh hd",
    "macintosh hd - data",
    "macos",
    "macos - data",
}


def _run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, capture_output=True, check=False)


def _diskutil_plist(args: list[str]) -> dict[str, Any]:
    """diskutil wants `-plist` immediately after the verb (`info -plist disk2`)."""
    if not args:
        return {}
    proc = _run(["diskutil", args[0], "-plist", *args[1:]])
    if proc.returncode != 0 or not proc.stdout:
        return {}
    try:
        data = plistlib.loads(proc.stdout)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _is_internal_volume(name: str, mount: str, info: dict[str, Any] | None = None) -> bool:
    mount_n = str(mount or "").rstrip("/") or "/"
    if mount_n in SYSTEM_MOUNTS or mount_n.startswith("/System/Volumes/"):
        return True
    if info and info.get("Internal"):
        return True
    return name.strip().lower() in INTERNAL_VOLUME_NAMES


def _is_usb_like(info: dict[str, Any]) -> bool:
    if info.get("Internal"):
        return False
    protocol = str(info.get("BusProtocol") or "").lower()
    if protocol in ("disk image", "pci", "pci-express", ""):
        return False
    return protocol in ("usb", "secure digital", "thunderbolt")


def _dev_ident(device: str) -> str:
    """Normalize diskutil ids. Do not use str.lstrip('/dev/') — it also strips the 'd' in diskN."""
    ident = str(device or "").strip()
    if ident.startswith("/dev/"):
        ident = ident[5:]
    return ident


def _mount_device(ident: str) -> str:
    ident = _dev_ident(ident)
    if not ident.startswith("disk"):
        return ""
    info = _diskutil_plist(["info", ident])
    mount = str(info.get("MountPoint") or "")
    if mount:
        return mount
    _run(["diskutil", "mount", ident])
    info = _diskutil_plist(["info", ident])
    mount = str(info.get("MountPoint") or "")
    if mount:
        return mount
    if not re.fullmatch(r"disk\d+(s\d+)?", ident):
        return ""
    subprocess.run(
        ["osascript", "-e", f'do shell script "diskutil mount {ident}" with administrator privileges'],
        capture_output=True,
        check=False,
    )
    info = _diskutil_plist(["info", ident])
    return str(info.get("MountPoint") or "")


def _whole_disk_id(ident: str) -> str:
    ident = _dev_ident(ident)
    match = re.match(r"(disk\d+)", ident)
    return match.group(1) if match else ident


def _efi_partition_for_disk(whole: str) -> str:
    listing = _diskutil_plist(["list", whole])
    disks = listing.get("AllDisksAndPartitions") or []
    node = disks[0] if disks else {}
    for part in node.get("Partitions") or []:
        if str(part.get("Content") or "") == "EFI":
            return str(part.get("DeviceIdentifier") or "")
    return ""


def _installer_volume_name(whole: str) -> str:
    listing = _diskutil_plist(["list", whole])
    disks = listing.get("AllDisksAndPartitions") or []
    node = disks[0] if disks else {}
    for part in node.get("Partitions") or []:
        name = str(part.get("VolumeName") or "")
        if name.lower().startswith("install macos"):
            return name
    return ""


def _ensure_external_efi_volumes() -> list[dict[str, Any]]:
    """Mount EFI partitions on external USB disks so they can receive OpenCore."""
    found: list[dict[str, Any]] = []
    listing = _diskutil_plist(["list", "external"])
    for disk in listing.get("AllDisksAndPartitions") or []:
        ident = str(disk.get("DeviceIdentifier") or "")
        if not re.fullmatch(r"disk\d+", ident):
            continue
        info = _diskutil_plist(["info", ident])
        if info.get("Internal") or not _is_usb_like(info):
            continue
        efi_id = ""
        for part in disk.get("Partitions") or []:
            if str(part.get("Content") or "") == "EFI":
                efi_id = str(part.get("DeviceIdentifier") or "")
                break
        if not efi_id:
            continue
        mount = _mount_device(efi_id)
        if not mount:
            continue
        efi_info = _diskutil_plist(["info", efi_id])
        parent = str(info.get("MediaName") or ident)
        installer = _installer_volume_name(ident)
        label = f"EFI — {installer or parent}"
        found.append({
            "kind": "volume",
            "name": label,
            "mountPoint": mount,
            "device": efi_id,
            "fileSystem": efi_info.get("FilesystemType") or "fat32",
            "size": efi_info.get("TotalSize") or 0,
            "ejectable": True,
            "writable": True,
            "role": "esp",
            "recommended": True,
            "hint": "OpenCore goes on this EFI partition. The macOS installer volume is left intact.",
        })
    return found


def list_usb_targets() -> dict[str, Any]:
    """Mounted USB volumes and EFI partitions that can receive an EFI folder."""
    volumes: list[dict[str, Any]] = []
    seen_mounts: set[str] = set()
    for efi_vol in _ensure_external_efi_volumes():
        volumes.append(efi_vol)
        seen_mounts.add(efi_vol["mountPoint"])

    volumes_root = Path("/Volumes")
    if volumes_root.exists():
        for item in sorted(volumes_root.iterdir()):
            if not item.is_dir() or item.name.startswith("."):
                continue
            mount = str(item)
            if mount in seen_mounts:
                continue
            info = _diskutil_plist(["info", mount])
            if not info or not info.get("DeviceIdentifier"):
                continue
            if _is_internal_volume(item.name, mount, info):
                continue
            if not _is_usb_like(info):
                continue
            if item.name in ("Shared Support", "macOS Base System"):
                continue
            content = str(info.get("Content") or "")
            is_esp = content == "EFI" or item.name.upper() == "EFI"
            installer = item.name.lower().startswith("install macos")
            whole = _whole_disk_id(str(info.get("DeviceIdentifier") or ""))
            sibling = _installer_volume_name(whole) if is_esp else ""
            display = f"EFI — {sibling}" if is_esp and sibling else item.name
            volumes.append({
                "kind": "volume",
                "name": display,
                "mountPoint": mount,
                "device": info.get("DeviceIdentifier") or "",
                "fileSystem": info.get("FilesystemType") or info.get("FilesystemName") or "",
                "size": info.get("TotalSize") or 0,
                "ejectable": bool(info.get("Ejectable")),
                "writable": True,
                "role": "esp" if is_esp else ("installer" if installer else "volume"),
                "recommended": is_esp,
                "hint": (
                    "OpenCore goes here. The macOS installer volume stays intact."
                    if is_esp
                    else (
                        "Installer volume. Prefer the EFI partition so createinstallmedia is not overwritten."
                        if installer
                        else ""
                    )
                ),
            })

    disks: list[dict[str, Any]] = []
    listing = _diskutil_plist(["list", "external"])
    for disk in listing.get("AllDisksAndPartitions") or []:
        ident = disk.get("DeviceIdentifier")
        if not ident or not re.fullmatch(r"disk\d+", str(ident)):
            continue
        info = _diskutil_plist(["info", ident])
        if info.get("Internal") or not _is_usb_like(info):
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


def _prefer_esp(mount_point: str) -> tuple[Path, str]:
    """If the selected volume is a macOS installer USB, copy onto its EFI partition instead."""
    dest_root = Path(mount_point)
    info = _diskutil_plist(["info", str(dest_root)])
    name = str(info.get("VolumeName") or dest_root.name)
    fs = str(info.get("FilesystemType") or "").lower()
    content = str(info.get("Content") or "")
    if content == "EFI" or name == "EFI" or fs in ("msdos", "fat32", "exfat"):
        return dest_root, ""
    if not str(name).lower().startswith("install macos"):
        return dest_root, ""
    ident = str(info.get("DeviceIdentifier") or "")
    whole = _whole_disk_id(ident)
    efi_id = _efi_partition_for_disk(whole)
    if not efi_id:
        return dest_root, ""
    mount = _mount_device(efi_id)
    if not mount:
        return dest_root, ""
    note = f"Installer volume left intact. OpenCore copied to EFI partition {efi_id} ({mount})."
    return Path(mount), note


def _replace_dir(src: Path, dest: Path) -> None:
    """Overwrite one folder. Leaves sibling folders (EFI/APPLE, Microsoft) alone."""
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    if dest.exists():
        for child in dest.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass
        try:
            dest.rmdir()
        except OSError:
            pass
    shutil.copytree(src, dest, dirs_exist_ok=True)


def _merge_efi_folder(efi_src: Path, dest_efi: Path) -> None:
    dest_efi.mkdir(parents=True, exist_ok=True)
    for child in efi_src.iterdir():
        if child.name.startswith("."):
            continue
        target = dest_efi / child.name
        if child.is_dir():
            _replace_dir(child, target)
        else:
            shutil.copy2(child, target)


def require_external_whole_disk(device: str) -> dict[str, Any]:
    ident = _dev_ident(device)
    if not re.fullmatch(r"disk\d+", ident):
        return {"success": False, "error": "Select a whole disk (diskN), not a partition (diskNsM)."}
    info = _diskutil_plist(["info", ident])
    if not info:
        return {"success": False, "error": f"diskutil could not inspect {ident}."}
    if info.get("Internal"):
        return {"success": False, "error": "Refusing to erase an internal disk."}
    if not _is_usb_like(info):
        return {"success": False, "error": f"{ident} does not look like removable USB storage."}
    size = int(info.get("TotalSize") or 0)
    return {
        "success": True,
        "ident": ident,
        "info": info,
        "name": info.get("MediaName") or ident,
        "size": size,
        "sizeLabel": f"{size / (1000 ** 3):.1f} GB" if size else "unknown",
    }


def copy_efi_to_disk_esp(device: str) -> dict[str, Any]:
    """Mount the ESP of a whole disk and merge the built OpenCore EFI."""
    ident = _dev_ident(device)
    whole = _whole_disk_id(ident)
    efi_id = _efi_partition_for_disk(whole)
    if not efi_id:
        return {"success": False, "error": f"No EFI partition found on {whole}."}
    mount = _mount_device(efi_id)
    if not mount:
        return {"success": False, "error": f"Could not mount EFI partition {efi_id}. Approve the admin prompt if it appears."}
    return copy_efi_to_volume(mount)


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

    info = _diskutil_plist(["info", str(dest_root)])
    if _is_internal_volume(dest_root.name, str(dest_root), info):
        return {"success": False, "error": "Refusing to write to an internal system volume."}

    dest_root, redirected = _prefer_esp(str(dest_root))
    dest_efi = dest_root / "EFI"
    _merge_efi_folder(efi_src, dest_efi)
    bootx = dest_efi / "BOOT" / "BOOTx64.efi"
    oc = dest_efi / "OC" / "OpenCore.efi"
    cfg = dest_efi / "OC" / "config.plist"
    message = f"Copied OpenCore to {dest_efi} (left other EFI folders in place)."
    if redirected:
        message = redirected
    return {
        "success": bootx.exists() and oc.exists() and cfg.exists(),
        "destination": str(dest_efi),
        "bootx64": bootx.exists(),
        "opencore": oc.exists(),
        "config": cfg.exists(),
        "message": message,
    }


def prepare_usb_and_copy(device: str, confirm: str) -> dict[str, Any]:
    """Erase an external disk as FAT32/GPT named OPENCORE, then copy EFI."""
    if str(confirm or "").strip() != "ERASE":
        return {"success": False, "error": "Pass confirm='ERASE' to wipe the selected external disk."}
    ident = _dev_ident(device)
    if not re.fullmatch(r"disk\d+", ident):
        return {"success": False, "error": "Select a whole disk (diskN), not a partition (diskNsM)."}
    info = _diskutil_plist(["info", ident])
    if not info:
        return {"success": False, "error": f"diskutil could not inspect {ident}."}
    if info.get("Internal"):
        return {"success": False, "error": "Refusing to erase an internal disk."}
    if not _is_usb_like(info):
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
