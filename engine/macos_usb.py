"""Build a macOS installer USB with OpenCore on the EFI partition.

Does not FAT32-erase the stick. Sequence matches the working manual path:
expand InstallAssistant.pkg → createinstallmedia → merge EFI/BOOT + EFI/OC.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .efi_builder import last_manifest
from .macos_downloader import _read_meta, installer_dir, local_file_state
from .usb_writer import copy_efi_to_disk_esp, require_external_whole_disk

STAGING_VOLUME = "OCSUSB"
MIN_USB_BYTES = 16 * 1000 ** 3
EXPAND_TIMEOUT = 45 * 60
WRITE_TIMEOUT = 90 * 60

_lock = threading.Lock()
_thread: threading.Thread | None = None
_job: dict[str, Any] = {
    "success": True,
    "status": "idle",
    "step": "",
    "percent": 0,
    "device": "",
    "installerId": "",
    "title": "",
    "appPath": "",
    "volume": "",
    "efiDestination": "",
    "error": None,
    "message": "No installer USB write in progress.",
    "log": "",
}


def _snapshot() -> dict[str, Any]:
    return dict(_job)


def _update(**kwargs: Any) -> dict[str, Any]:
    _job.update(kwargs)
    return _snapshot()


def usb_job_status() -> dict[str, Any]:
    with _lock:
        return _snapshot()


def _append_log(line: str) -> None:
    prev = str(_job.get("log") or "")
    text = f"{prev}\n{line}".strip()
    _job["log"] = text[-8000:]
    _job["message"] = line


def _run_admin(argv: list[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    cmd = " ".join(shlex.quote(part) for part in argv)
    script = f"do shell script {json.dumps(cmd)} with administrator privileges"
    return subprocess.run(["osascript", "-e", script], capture_output=True, timeout=timeout, check=False)


def _decode(proc: subprocess.CompletedProcess[bytes]) -> str:
    out = (proc.stdout or b"") + b"\n" + (proc.stderr or b"")
    return out.decode("utf-8", errors="replace").strip()


def _installer_app_name(installer_id: str) -> str:
    meta = _read_meta(installer_id) or {}
    title = str(meta.get("title") or "").strip()
    if title.lower().startswith("macos "):
        return f"Install {title}.app"
    name = str(meta.get("name") or "").strip()
    if name:
        return f"Install macOS {name}.app"
    return "Install macOS.app"


def _assembled_app(installer_id: str) -> Path:
    return installer_dir(installer_id) / _installer_app_name(installer_id)


def _createinstallmedia(app: Path) -> Path:
    return app / "Contents" / "Resources" / "createinstallmedia"


def _shared_support(app: Path) -> Path:
    return app / "Contents" / "SharedSupport" / "SharedSupport.dmg"


def installer_app_ready(installer_id: str) -> dict[str, Any]:
    app = _assembled_app(installer_id)
    tool = _createinstallmedia(app)
    dmg = _shared_support(app)
    ready = tool.exists() and dmg.exists() and dmg.stat().st_size > 1024 ** 3
    return {
        "success": ready,
        "appPath": str(app) if app.exists() else "",
        "createinstallmedia": str(tool) if tool.exists() else "",
        "sharedSupportBytes": dmg.stat().st_size if dmg.exists() else 0,
    }


def _wait_for_mount(name: str, seconds: int = 40) -> Path | None:
    path = Path("/Volumes") / name
    deadline = time.time() + seconds
    while time.time() < deadline:
        if path.exists():
            return path
        time.sleep(1)
    return path if path.exists() else None


def _find_installer_volume() -> str:
    root = Path("/Volumes")
    if not root.exists():
        return ""
    for item in sorted(root.iterdir()):
        if item.name.lower().startswith("install macos"):
            return str(item)
    return ""


def assemble_installer_app(installer_id: str) -> dict[str, Any]:
    """Expand InstallAssistant.pkg into a createinstallmedia-ready .app."""
    local = local_file_state(installer_id)
    if local.get("status") != "complete":
        return {"success": False, "error": "Download a complete InstallAssistant.pkg first."}
    pkg = Path(local["localPath"])
    if not pkg.exists():
        return {"success": False, "error": f"Missing pkg: {pkg}"}

    already = installer_app_ready(installer_id)
    if already["success"]:
        return {**already, "reused": True, "message": "Installer app already assembled."}

    app = _assembled_app(installer_id)
    # pkgutil --expand-full requires the destination to not exist.
    expanded = pkg.parent / "expanded"
    if expanded.exists():
        if expanded.is_dir():
            shutil.rmtree(expanded)
        else:
            expanded.unlink()
    if expanded.exists():
        return {"success": False, "error": f"Could not clear leftover expand folder: {expanded}"}

    proc = subprocess.run(
        ["pkgutil", "--expand-full", str(pkg), str(expanded)],
        capture_output=True,
        timeout=EXPAND_TIMEOUT,
        check=False,
    )
    if proc.returncode != 0:
        err = _decode(proc) or "pkgutil --expand-full failed."
        return {"success": False, "error": err}

    payload_app = None
    for candidate in expanded.rglob("*.app"):
        if (candidate / "Contents/Resources/createinstallmedia").exists():
            payload_app = candidate
            break
    dmg = expanded / "SharedSupport.dmg"
    if not dmg.exists():
        found = list(expanded.rglob("SharedSupport.dmg"))
        dmg = found[0] if found else dmg
    if payload_app is None or not dmg.exists():
        return {"success": False, "error": "Expanded pkg did not contain Install macOS.app + SharedSupport.dmg."}

    if app.exists():
        shutil.rmtree(app, ignore_errors=True)
    app.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(payload_app, app)
    dest_dmg = _shared_support(app)
    dest_dmg.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(dmg), str(dest_dmg))
    shutil.rmtree(expanded, ignore_errors=True)

    ready = installer_app_ready(installer_id)
    if not ready["success"]:
        return {"success": False, "error": "Assembler finished but createinstallmedia/SharedSupport is missing."}
    return {**ready, "reused": False, "message": f"Assembled {app.name}."}


def _worker(device: str, installer_id: str) -> None:
    try:
        with _lock:
            _append_log("Checking EFI build and installer pkg…")
            _update(status="running", step="validate", percent=5, error=None)

        manifest = last_manifest()
        if not manifest.get("success"):
            raise RuntimeError("Build an EFI folder first.")

        disk = require_external_whole_disk(device)
        if not disk.get("success"):
            raise RuntimeError(disk.get("error") or "Invalid disk.")
        if int(disk.get("size") or 0) < MIN_USB_BYTES:
            raise RuntimeError(f"USB is too small ({disk.get('sizeLabel')}). Need about 16 GB or more.")
        ident = disk["ident"]

        local = local_file_state(installer_id)
        if local.get("status") != "complete":
            raise RuntimeError("Download the selected macOS installer first.")
        meta = _read_meta(installer_id) or {}
        title = str(meta.get("title") or meta.get("name") or installer_id)
        with _lock:
            _update(title=title, device=ident)

        with _lock:
            _append_log("Expanding InstallAssistant.pkg (several minutes)…")
            _update(step="expand", percent=12)
        assembled = assemble_installer_app(installer_id)
        if not assembled.get("success"):
            raise RuntimeError(assembled.get("error") or "Could not assemble the installer app.")
        app = Path(assembled["appPath"])
        tool = _createinstallmedia(app)
        with _lock:
            _update(appPath=str(app), percent=35)
            _append_log(assembled.get("message") or f"Using {app.name}")

        with _lock:
            _append_log(f"Erasing {ident} as Mac OS Extended (Journaled). Approve the password dialog if asked.")
            _update(step="erase", percent=40)
        erase = _run_admin(["diskutil", "eraseDisk", "JHFS+", STAGING_VOLUME, "GPT", ident], timeout=180)
        if erase.returncode != 0:
            # Some USBs erase without admin.
            fallback = subprocess.run(
                ["diskutil", "eraseDisk", "JHFS+", STAGING_VOLUME, "GPT", ident],
                capture_output=True,
                timeout=180,
                check=False,
            )
            if fallback.returncode != 0:
                raise RuntimeError(_decode(erase) or _decode(fallback) or "diskutil eraseDisk failed.")
        volume = _wait_for_mount(STAGING_VOLUME)
        if volume is None:
            raise RuntimeError(f"Disk was erased but /Volumes/{STAGING_VOLUME} did not appear.")

        with _lock:
            _append_log("Writing macOS installer with createinstallmedia. This can take 10–40 minutes.")
            _update(step="createinstallmedia", percent=48)
        write = _run_admin([str(tool), "--volume", str(volume), "--nointeraction"], timeout=WRITE_TIMEOUT)
        text = _decode(write)
        with _lock:
            if text:
                _append_log(text.splitlines()[-1][:400])
        if write.returncode != 0:
            raise RuntimeError(text or "createinstallmedia failed.")

        installer_vol = _find_installer_volume()
        with _lock:
            _update(volume=installer_vol, step="efi", percent=88)
            _append_log("Copying OpenCore onto the EFI partition…")
        copied = copy_efi_to_disk_esp(ident)
        if not copied.get("success"):
            raise RuntimeError(
                f"macOS installer is on the USB, but OpenCore copy failed: {copied.get('error')}"
            )

        with _lock:
            _update(
                status="done",
                step="done",
                percent=100,
                success=True,
                efiDestination=copied.get("destination") or "",
                error=None,
            )
            _append_log(copied.get("message") or "OpenCore copied to the EFI partition.")
            _append_log("USB is ready: macOS installer + OpenCore. Boot it in UEFI mode.")
    except subprocess.TimeoutExpired:
        with _lock:
            _update(status="error", success=False, error="Timed out writing the installer USB.")
            _append_log("Timed out.")
    except Exception as exc:
        with _lock:
            _update(status="error", success=False, error=str(exc))
            _append_log(str(exc))


def start_macos_usb(device: str, installer_id: str, confirm: str) -> dict[str, Any]:
    global _thread
    if str(confirm or "").strip() != "INSTALL":
        return {"success": False, "error": "Type INSTALL to confirm this will wipe the selected USB and write macOS + OpenCore."}
    installer_id = str(installer_id or "").strip()
    if not installer_id:
        return {"success": False, "error": "Select a downloaded macOS installer."}

    disk = require_external_whole_disk(device)
    if not disk.get("success"):
        return disk
    if int(disk.get("size") or 0) < MIN_USB_BYTES:
        return {"success": False, "error": f"USB is too small ({disk.get('sizeLabel')}). Need about 16 GB or more."}

    manifest = last_manifest()
    if not manifest.get("success"):
        return {"success": False, "error": "Build an EFI folder first."}
    local = local_file_state(installer_id)
    if local.get("status") != "complete":
        return {"success": False, "error": "Download the selected macOS installer first."}

    with _lock:
        if _job.get("status") == "running":
            return {**_snapshot(), "success": False, "error": "An installer USB write is already running."}
        _update(
            success=True,
            status="running",
            step="starting",
            percent=1,
            device=disk["ident"],
            installerId=installer_id,
            title="",
            appPath="",
            volume="",
            efiDestination="",
            error=None,
            log="",
            message="Starting macOS + OpenCore USB write…",
        )
        _thread = threading.Thread(target=_worker, args=(disk["ident"], installer_id), daemon=True)
        _thread.start()
        return _snapshot()
