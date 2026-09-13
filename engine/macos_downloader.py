"""Download one selected macOS InstallAssistant.pkg into the local cache.

Catalog listing stays metadata-only. A download starts only when the user
picks an installer. Incomplete files are kept as .part so they can resume.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from .macos_catalog import CACHE_DIR, _now, _size_label, list_macos_installers

INSTALLERS_DIR = CACHE_DIR / "macos-installers"
STATE_PATH = CACHE_DIR / "macos-download.json"
PKG_NAME = "InstallAssistant.pkg"
CHUNK_SIZE = 1024 * 1024
PROGRESS_INTERVAL = 0.4
DISK_BUFFER = 256 * 1024 * 1024
USER_AGENT = "OpenCoreStudio-macOSDownload/1.0"

_lock = threading.Lock()
_cancel = threading.Event()
_thread: threading.Thread | None = None
_job: dict[str, Any] = {
    "success": True,
    "status": "idle",
    "id": "",
    "title": "",
    "version": "",
    "build": "",
    "sizeBytes": 0,
    "sizeLabel": "",
    "pkgUrl": "",
    "localPath": "",
    "bytesReceived": 0,
    "bytesTotal": 0,
    "percent": 0,
    "speedBps": 0,
    "etaSeconds": None,
    "error": None,
    "startedAt": "",
    "updatedAt": "",
    "finishedAt": None,
    "resumed": False,
    "message": "No installer download in progress.",
}


def _iso() -> str:
    return _now().replace(microsecond=0).isoformat()


def _safe_id(installer_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", installer_id or "").strip("._")
    return cleaned or "installer"


def installer_dir(installer_id: str) -> Path:
    return INSTALLERS_DIR / _safe_id(installer_id)


def pkg_path(installer_id: str) -> Path:
    return installer_dir(installer_id) / PKG_NAME


def part_path(installer_id: str) -> Path:
    return installer_dir(installer_id) / f"{PKG_NAME}.part"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _snapshot() -> dict[str, Any]:
    return dict(_job)


def _persist_job() -> None:
    try:
        _write_json(STATE_PATH, _snapshot())
    except Exception:
        pass


def _update_job(**kwargs: Any) -> dict[str, Any]:
    _job.update(kwargs)
    _job["updatedAt"] = _iso()
    _persist_job()
    return _snapshot()


def _find_catalog_item(installer_id: str) -> dict[str, Any] | None:
    wanted = (installer_id or "").strip()
    if not wanted:
        return None
    data = list_macos_installers(refresh=False)
    for item in data.get("installers") or []:
        if item.get("id") == wanted or item.get("productId") == wanted:
            return item
    return None


def _meta_path(installer_id: str) -> Path:
    return installer_dir(installer_id) / "meta.json"


def _read_meta(installer_id: str) -> dict[str, Any] | None:
    path = _meta_path(installer_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_meta(item: dict[str, Any], extra: dict[str, Any] | None = None) -> None:
    payload = {
        "id": item.get("id"),
        "productId": item.get("productId"),
        "title": item.get("title"),
        "name": item.get("name"),
        "version": item.get("version"),
        "build": item.get("build"),
        "sizeBytes": item.get("sizeBytes") or 0,
        "pkgUrl": item.get("pkgUrl"),
        "downloadedAt": _iso(),
        "pkgName": PKG_NAME,
    }
    if extra:
        payload.update(extra)
    _write_json(_meta_path(item["id"]), payload)


def local_file_state(installer_id: str) -> dict[str, Any]:
    final = pkg_path(installer_id)
    part = part_path(installer_id)
    meta = _read_meta(installer_id) or {}
    expected = int(meta.get("sizeBytes") or 0)
    if final.exists() and final.stat().st_size > 0:
        size = final.stat().st_size
        complete = (not expected) or size == expected
        return {
            "status": "complete" if complete else "error",
            "bytesReceived": size,
            "bytesTotal": expected or size,
            "localPath": str(final),
            "error": None if complete else f"Cached pkg is {size} bytes, expected {expected}.",
        }
    if part.exists() and part.stat().st_size > 0:
        size = part.stat().st_size
        return {
            "status": "partial",
            "bytesReceived": size,
            "bytesTotal": expected,
            "localPath": str(part),
            "error": None,
        }
    return {
        "status": "none",
        "bytesReceived": 0,
        "bytesTotal": expected,
        "localPath": "",
        "error": None,
    }


def list_cached_installers() -> list[dict[str, Any]]:
    if not INSTALLERS_DIR.exists():
        return []
    found = []
    for folder in sorted(INSTALLERS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        meta = _read_meta(folder.name) or {"id": folder.name}
        state = local_file_state(meta.get("id") or folder.name)
        found.append({**meta, **state})
    return found


def attach_local_downloads(payload: dict[str, Any]) -> dict[str, Any]:
    """Stamp catalog rows with cache / in-flight download state."""
    active_id = ""
    active_status = "idle"
    with _lock:
        if _job.get("status") == "downloading":
            active_id = _job.get("id") or ""
            active_status = "downloading"
    downloaded = 0
    for item in payload.get("installers") or []:
        local = local_file_state(item.get("id") or "")
        status = local["status"]
        if active_id and item.get("id") == active_id:
            status = active_status
        item["downloadStatus"] = status
        item["downloadedBytes"] = local["bytesReceived"]
        item["localPath"] = local["localPath"]
        if status == "complete":
            downloaded += 1
    payload["downloadedCount"] = downloaded
    payload["downloadCacheDir"] = str(INSTALLERS_DIR)
    return payload


def download_status() -> dict[str, Any]:
    with _lock:
        job = _snapshot()
    if job.get("id") and job.get("status") in ("idle", "cancelled", "error"):
        local = local_file_state(job["id"])
        if local["status"] == "complete":
            job = {**job, **local, "success": True, "percent": 100}
    job["cached"] = list_cached_installers()
    return job


def cancel_download() -> dict[str, Any]:
    with _lock:
        if _job.get("status") != "downloading":
            return {**_snapshot(), "success": True, "message": "No download to cancel."}
        _cancel.set()
        return _update_job(message="Cancel requested…")


def remove_partial(installer_id: str) -> dict[str, Any]:
    """Delete a leftover .part file. Refuses complete pkgs and in-flight downloads."""
    wanted = (installer_id or "").strip()
    if not wanted:
        return {"success": False, "error": "Provide an installer id.", "status": "error"}

    with _lock:
        if _job.get("status") == "downloading" and _job.get("id") == wanted:
            return {
                "success": False,
                "error": "Cancel the download before removing the partial file.",
                **_snapshot(),
            }

    local = local_file_state(wanted)
    if local["status"] == "complete":
        return {
            "success": False,
            "error": "That installer is fully downloaded. Only partial files can be removed.",
            "status": "complete",
            "id": wanted,
        }
    if local["status"] not in ("partial", "error"):
        return {
            "success": False,
            "error": "No partial download to remove.",
            "status": local["status"],
            "id": wanted,
        }

    dest = installer_dir(wanted)
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    with _lock:
        if _job.get("id") == wanted:
            return _update_job(
                success=True,
                status="idle",
                bytesReceived=0,
                bytesTotal=_job.get("sizeBytes") or 0,
                percent=0,
                speedBps=0,
                etaSeconds=None,
                localPath="",
                error=None,
                finishedAt=_iso(),
                message="Removed the partial download.",
            )
    return {
        "success": True,
        "status": "idle",
        "id": wanted,
        "message": "Removed the partial download.",
    }


def _check_disk(dest_dir: Path, needed: int) -> None:
    if needed <= 0:
        return
    free = shutil.disk_usage(dest_dir).free
    if free < needed + DISK_BUFFER:
        raise RuntimeError(
            f"Not enough free disk space. Need {_size_label(needed)} plus headroom, "
            f"have {_size_label(free)}."
        )


def _open_pkg(url: str, start: int):
    headers = {"User-Agent": USER_AGENT}
    if start > 0:
        headers["Range"] = f"bytes={start}-"
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=120)


def _run_download(item: dict[str, Any]) -> None:
    installer_id = item["id"]
    dest_dir = installer_dir(installer_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = pkg_path(installer_id)
    part = part_path(installer_id)
    expected = int(item.get("sizeBytes") or 0)
    start = part.stat().st_size if part.exists() else 0
    resumed = start > 0

    try:
        _check_disk(dest_dir, max(expected - start, 0))
        resp = _open_pkg(item["pkgUrl"], start)
        http_status = getattr(resp, "status", 200)
        if start and http_status == 200:
            start = 0
            resumed = False
            part.unlink(missing_ok=True)

        content_len = resp.headers.get("Content-Length")
        if start and http_status == 206 and content_len:
            total = start + int(content_len)
        elif content_len and http_status != 206:
            total = int(content_len)
        else:
            total = expected or start

        with _lock:
            _update_job(
                status="downloading",
                resumed=resumed,
                bytesReceived=start,
                bytesTotal=total or expected,
                percent=int((start * 100) / total) if total else 0,
                message=(
                    f"{'Resuming' if resumed else 'Downloading'} "
                    f"{item.get('title')} {item.get('version')}…"
                ),
            )

        received = start
        last_t = time.monotonic()
        last_bytes = start
        mode = "ab" if start else "wb"
        with open(part, mode) as handle:
            while True:
                if _cancel.is_set():
                    with _lock:
                        _update_job(
                            status="cancelled",
                            finishedAt=_iso(),
                            speedBps=0,
                            etaSeconds=None,
                            message="Download cancelled. Partial file kept for resume.",
                        )
                    return
                chunk = resp.read(CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
                received += len(chunk)
                now = time.monotonic()
                if now - last_t >= PROGRESS_INTERVAL:
                    elapsed = now - last_t
                    speed = (received - last_bytes) / elapsed if elapsed else 0
                    remaining = max(total - received, 0) if total else 0
                    eta = int(remaining / speed) if speed and remaining else None
                    percent = int((received * 100) / total) if total else 0
                    with _lock:
                        _update_job(
                            bytesReceived=received,
                            bytesTotal=total or expected,
                            percent=min(percent, 99),
                            speedBps=int(speed),
                            etaSeconds=eta,
                            message=(
                                f"Downloading {item.get('title')} {item.get('version')} "
                                f"({_size_label(received)}"
                                f"{' / ' + _size_label(total) if total else ''})"
                            ),
                        )
                    last_t = now
                    last_bytes = received

        if expected and received != expected:
            raise RuntimeError(
                f"Size mismatch after download: got {received} bytes, expected {expected}."
            )
        if received <= 0:
            raise RuntimeError("Download finished with an empty file.")

        part.replace(final)
        _write_meta(item, {"bytesReceived": received, "status": "complete"})
        with _lock:
            _update_job(
                success=True,
                status="complete",
                bytesReceived=received,
                bytesTotal=expected or received,
                percent=100,
                speedBps=0,
                etaSeconds=0,
                localPath=str(final),
                finishedAt=_iso(),
                error=None,
                message=f"Cached {item.get('title')} {item.get('version')} at {final}",
            )
    except Exception as exc:
        if _cancel.is_set():
            return
        err = str(exc)
        if "HTTP Error" in err:
            err = f"Apple CDN rejected the package download ({err})."
        with _lock:
            _update_job(
                success=False,
                status="error",
                error=err,
                finishedAt=_iso(),
                speedBps=0,
                etaSeconds=None,
                message=err,
            )


def start_download(installer_id: str) -> dict[str, Any]:
    wanted = (installer_id or "").strip()
    if not wanted:
        return {"success": False, "error": "Provide an installer id.", "status": "error"}

    item = _find_catalog_item(wanted)
    if not item:
        return {"success": False, "error": f"Unknown installer '{wanted}'.", "status": "error"}
    if not item.get("pkgUrl"):
        return {"success": False, "error": "Catalog entry has no package URL.", "status": "error"}

    local = local_file_state(item["id"])
    if local["status"] == "complete":
        with _lock:
            return _update_job(
                success=True,
                status="complete",
                id=item["id"],
                title=item.get("title") or "",
                version=item.get("version") or "",
                build=item.get("build") or "",
                sizeBytes=item.get("sizeBytes") or 0,
                sizeLabel=item.get("sizeLabel") or "",
                pkgUrl=item.get("pkgUrl") or "",
                localPath=local["localPath"],
                bytesReceived=local["bytesReceived"],
                bytesTotal=local["bytesTotal"],
                percent=100,
                speedBps=0,
                etaSeconds=0,
                error=None,
                finishedAt=_iso(),
                message=f"Already cached at {local['localPath']}",
            )

    global _thread
    with _lock:
        if _job.get("status") == "downloading":
            if _job.get("id") == item["id"]:
                return {**_snapshot(), "success": True}
            return {
                "success": False,
                "error": f"Already downloading {_job.get('title')} {_job.get('version')}. Cancel it first.",
                **_snapshot(),
            }
        _cancel.clear()
        _update_job(
            success=True,
            status="downloading",
            id=item["id"],
            title=item.get("title") or "",
            version=item.get("version") or "",
            build=item.get("build") or "",
            sizeBytes=item.get("sizeBytes") or 0,
            sizeLabel=item.get("sizeLabel") or "",
            pkgUrl=item.get("pkgUrl") or "",
            localPath=str(part_path(item["id"])),
            bytesReceived=local["bytesReceived"],
            bytesTotal=item.get("sizeBytes") or 0,
            percent=0,
            speedBps=0,
            etaSeconds=None,
            error=None,
            startedAt=_iso(),
            finishedAt=None,
            resumed=local["status"] == "partial",
            message=f"Starting {item.get('title')} {item.get('version')}…",
        )
        _thread = threading.Thread(target=_run_download, args=(item,), daemon=True)
        _thread.start()
        return _snapshot()
