"""First-open OpenCore version picker for a portable Studio.app.

Seeds Application Support, lists GitHub releases, and waits for the user to
keep the included Sample, take the latest, or pick an older tag.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .efi_builder import prefetch_opencore_release
from .paths import first_run_path, mutable_file, uses_portable_store, work_dir
from .updater import (
    SAMPLE_PLIST_PATH,
    _sha256_bytes,
    _sha256_file,
    apply_updates,
    fetch_opencore_releases,
    fetch_sample_plist,
    load_state,
    local_status,
)

SEED_FILES = ("Sample.plist", "amd_patches.plist", "kexts.json", "repos.json")
BUNDLED_FALLBACK_TAG = "1.0.7"
IDENTIFY_LIMIT = 8


def _load_first_run() -> dict[str, Any]:
    path = first_run_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_first_run(data: dict[str, Any]) -> None:
    first_run_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def seed_portable_files() -> list[str]:
    seeded = []
    for name in SEED_FILES:
        path = mutable_file(name)
        if path.exists():
            seeded.append(name)
    return seeded


def _stable_releases(limit: int = 20) -> list[dict[str, Any]]:
    releases = fetch_opencore_releases(limit=limit)
    return [item for item in releases if not item.get("prerelease") and item.get("tag")]


def _identify_included_tag(releases: list[dict[str, Any]]) -> str:
    local_sha = _sha256_file(SAMPLE_PLIST_PATH)
    if local_sha:
        for item in releases[:IDENTIFY_LIMIT]:
            try:
                raw = fetch_sample_plist(item["tag"])
            except Exception:
                continue
            if _sha256_bytes(raw) == local_sha:
                return item["tag"]
    state_tag = str((load_state().get("opencore") or {}).get("tag") or "")
    if state_tag and state_tag not in ("bundled", "rolled-back"):
        return state_tag
    return BUNDLED_FALLBACK_TAG


def prepare_first_open(force: bool = False) -> dict[str, Any]:
    """Seed files and return the version picker. Does not apply updates."""
    seeded = seed_portable_files()
    previous = _load_first_run()
    if previous.get("completed") and previous.get("chosenTag") and not force:
        return {
            "success": True,
            "needsChoice": False,
            "alreadyReady": True,
            "portable": uses_portable_store(),
            "workDir": str(work_dir()),
            "firstRun": previous,
            "schema": local_status(),
        }

    payload: dict[str, Any] = {
        "success": True,
        "needsChoice": True,
        "alreadyReady": False,
        "portable": uses_portable_store(),
        "workDir": str(work_dir()),
        "seeded": seeded,
        "includedTag": BUNDLED_FALLBACK_TAG,
        "latestTag": "",
        "hasNewer": False,
        "releases": [],
        "offline": False,
        "errors": [],
        "schema": local_status(),
        "message": "Choose which OpenCore Sample this Mac should use.",
    }

    if not uses_portable_store() and not force:
        payload["needsChoice"] = False
        payload["alreadyReady"] = True
        payload["message"] = "Source-tree session; the version picker is for the .app."
        return payload

    try:
        releases = _stable_releases()
        payload["releases"] = [
            {"tag": item["tag"], "publishedAt": item.get("publishedAt") or ""}
            for item in releases
        ]
        payload["includedTag"] = _identify_included_tag(releases)
        if releases:
            payload["latestTag"] = releases[0]["tag"]
        payload["hasNewer"] = bool(
            payload["latestTag"] and payload["latestTag"] != payload["includedTag"]
        )
        if payload["hasNewer"]:
            payload["message"] = (
                f"This app includes OpenCore {payload['includedTag']}. "
                f"Latest on GitHub is {payload['latestTag']}."
            )
        else:
            payload["message"] = (
                f"This app includes OpenCore {payload['includedTag']}, which is the latest release."
            )
    except Exception as exc:
        payload["offline"] = True
        payload["errors"].append(str(exc))
        payload["message"] = (
            f"This app includes OpenCore {payload['includedTag']}. "
            "GitHub is unreachable — you can keep that version."
        )
    return payload


def choose_first_open(opencore_tag: str) -> dict[str, Any]:
    """Apply the chosen OpenCore tag, refresh kext/AMD metadata, cache the RELEASE zip."""
    seed_portable_files()
    tag = (opencore_tag or "").strip()
    if not tag:
        return {"success": False, "error": "Pick an OpenCore version."}

    errors: list[str] = []
    applied: dict[str, Any] = {}
    cached: dict[str, Any] = {}

    try:
        result = apply_updates(["opencore", "amd", "kexts"], opencore_tag=tag)
        applied = result.get("applied") or {}
        errors.extend(result.get("errors") or [])
    except Exception as exc:
        errors.append(str(exc))

    try:
        zip_path = prefetch_opencore_release(tag)
        cached["opencoreZip"] = str(zip_path)
        cached["opencoreTag"] = tag
    except Exception as exc:
        errors.append(f"OpenCore zip: {exc}")

    record = {
        "completed": True,
        "chosenTag": tag,
        "completedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "opencoreTag": (load_state().get("opencore") or {}).get("tag") or tag,
        "ocZipCached": bool(cached.get("opencoreZip")),
        "errors": errors,
    }
    _save_first_run(record)
    return {
        "success": True,
        "needsChoice": False,
        "alreadyReady": True,
        "chosenTag": tag,
        "applied": applied,
        "cached": cached,
        "errors": errors,
        "firstRun": record,
        "schema": local_status(),
        "message": f"Using OpenCore {tag}. Sample and kext versions are ready on this Mac.",
    }


def run_first_open(force: bool = False) -> dict[str, Any]:
    """Back-compat: only prepare the picker. Apply happens via choose_first_open."""
    return prepare_first_open(force=force)
