"""Persist the last Studio editing session across app launches.

WKWebView localStorage is keyed by origin, and the native app can bind a new
localhost port each start — so browser storage alone drops the last profile.
This file lives in Application Support (or the data dir in source-tree runs).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .paths import work_dir

SESSION_NAME = "studio-session.json"
ALLOWED_KEYS = {
    "savedAt",
    "profileId",
    "gpuId",
    "cpuFilter",
    "selectedKexts",
    "selectedKextIds",
    "selectedDrivers",
    "selectedSsdts",
    "selectedAcpiPatches",
    "secureBootModel",
    "bootArgs",
    "smbios",
    "quirks",
    "kernelEmulate",
    "amdCoreCount",
    "latestXml",
    "selectedMacosId",
}


def session_path():
    return work_dir() / SESSION_NAME


def load_studio_session() -> dict[str, Any]:
    path = session_path()
    if not path.exists():
        return {"success": True, "session": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"success": False, "session": None, "error": f"Could not read session: {exc}"}
    if not isinstance(data, dict) or not data.get("profileId"):
        return {"success": True, "session": None}
    return {"success": True, "session": data}


def save_studio_session(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"success": False, "error": "Session payload must be an object."}
    data = {key: payload[key] for key in ALLOWED_KEYS if key in payload}
    profile_id = str(data.get("profileId") or "").strip()
    if not profile_id:
        return {"success": False, "error": "Session is missing profileId."}
    data["profileId"] = profile_id
    data["savedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    kexts = data.get("selectedKexts") or data.get("selectedKextIds") or []
    if isinstance(kexts, list):
        data["selectedKexts"] = kexts
        data["selectedKextIds"] = kexts
    path = session_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"success": True, "session": data, "path": str(path)}


def clear_studio_session() -> dict[str, Any]:
    path = session_path()
    try:
        path.unlink(missing_ok=True)
    except TypeError:
        if path.exists():
            path.unlink()
    except OSError as exc:
        return {"success": False, "error": str(exc)}
    return {"success": True, "session": None}
