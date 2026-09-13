"""OpenCore Studio — Hardware Profiles Engine.

Loads base system templates (CPU, Motherboard, GPU, Audio, Network), provides
recommended configurations, and supports importing live rule updates.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = ROOT_DIR / "data" / "profiles"


def list_profiles() -> list[dict[str, Any]]:
    """Returns summaries of all available hardware profiles."""
    profiles = []
    if not PROFILES_DIR.exists():
        return []

    for file_path in sorted(PROFILES_DIR.glob("*.json")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                profiles.append({
                    "id": data.get("id", file_path.stem),
                    "name": data.get("name", file_path.stem),
                    "platform": data.get("platform", "desktop"),
                    "architecture": data.get("architecture", ""),
                    "cpuFamily": data.get("cpuFamily", ""),
                    "chipsets": data.get("chipsets", []),
                    "description": data.get("description", ""),
                    "examples": data.get("examples", []),
                    "searchTerms": data.get("searchTerms", []),
                    "file": file_path.name
                })
        except Exception:
            continue
    return profiles


def get_profile(profile_id: str) -> dict[str, Any] | None:
    """Loads a full hardware profile by ID."""
    target = PROFILES_DIR / f"{profile_id}.json"
    if not target.exists():
        # Search by 'id' attribute inside files
        for p in PROFILES_DIR.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("id") == profile_id:
                        return data
            except Exception:
                continue
        return None

    with open(target, "r", encoding="utf-8") as f:
        return json.load(f)


def import_profile_from_url(url: str) -> dict[str, Any]:
    """Fetches a hardware profile JSON from a remote URL and saves it."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OpenCoreStudio"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            data = json.loads(content)

        profile_id = str(data.get("id") or "").strip()
        if not profile_id:
            return {"success": False, "error": "Imported profile JSON is missing mandatory 'id' field."}

        target = PROFILES_DIR / f"{profile_id}.json"
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return {"success": True, "profile": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


def import_profile_from_json(data: dict[str, Any]) -> dict[str, Any]:
    """Imports and validates a hardware profile from a JSON dictionary."""
    try:
        profile_id = str(data.get("id") or "").strip()
        if not profile_id:
            return {"success": False, "error": "Profile JSON is missing mandatory 'id' field."}

        target = PROFILES_DIR / f"{profile_id}.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return {"success": True, "profile": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_custom_profile(data: dict[str, Any]) -> dict[str, Any]:
    """Saves or updates a hardware profile locally."""
    return import_profile_from_json(data)
