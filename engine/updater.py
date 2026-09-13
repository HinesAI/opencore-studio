"""OpenCore Studio — Upstream update engine.

Pulls newer Acidanthera Sample.plist schemas, AMD Vanilla kernel patches, and
kext release tags without requiring an app rebuild.
"""

from __future__ import annotations

import hashlib
import json
import plistlib
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .kext_manager import fetch_latest_release, load_kext_catalog
from .paths import backups_dir, data_dir, mutable_file, work_dir

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = data_dir()
BACKUP_DIR = backups_dir()
STATE_FILE = work_dir() / "update-state.json"
SAMPLE_PLIST_PATH = mutable_file("Sample.plist")
AMD_PATCHES_PATH = mutable_file("amd_patches.plist")
KEXTS_FILE = mutable_file("kexts.json")

OPENCORE_REPO = "acidanthera/OpenCorePkg"
AMD_VANILLA_REPO = "AMD-OSX/AMD_Vanilla"
REQUIRED_SAMPLE_SECTIONS = (
    "ACPI",
    "Booter",
    "DeviceProperties",
    "Kernel",
    "Misc",
    "NVRAM",
    "PlatformInfo",
    "UEFI",
)
USER_AGENT = "OpenCoreStudio-Updater/1.0"
MAX_BACKUPS = 8


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    return _sha256_bytes(path.read_bytes())


def _http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json, application/octet-stream, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _github_json(url: str) -> Any:
    return json.loads(_http_get(url).decode("utf-8"))


def default_state() -> dict[str, Any]:
    return {
        "opencore": {
            "tag": "bundled",
            "source": "bundled",
            "sampleSha256": _sha256_file(SAMPLE_PLIST_PATH),
            "appliedAt": None,
            "notes": "",
        },
        "amdVanilla": {
            "ref": "bundled",
            "sha256": _sha256_file(AMD_PATCHES_PATH),
            "appliedAt": None,
        },
        "kexts": {
            "lastChecked": None,
            "lastApplied": None,
        },
        "lastCheck": None,
        "canRollback": False,
    }


def load_state() -> dict[str, Any]:
    state = default_state()
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for key, value in saved.items():
                if isinstance(value, dict) and isinstance(state.get(key), dict):
                    state[key].update(value)
                else:
                    state[key] = value
        except (OSError, json.JSONDecodeError):
            pass
    if not state["opencore"].get("sampleSha256"):
        state["opencore"]["sampleSha256"] = _sha256_file(SAMPLE_PLIST_PATH)
    if not state["amdVanilla"].get("sha256"):
        state["amdVanilla"]["sha256"] = _sha256_file(AMD_PATCHES_PATH)
    return state


def save_state(state: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def current_schema_label(state: dict[str, Any] | None = None) -> str:
    state = state or load_state()
    tag = str(state.get("opencore", {}).get("tag") or "bundled")
    if tag == "bundled":
        return "OpenCore bundled Sample.plist"
    return f"OpenCore {tag} Sample.plist"


def get_sample_schema() -> dict[str, Any]:
    """Expose quirk defaults and section keys from the active Sample.plist."""
    if not SAMPLE_PLIST_PATH.exists():
        return {"success": False, "error": "Sample.plist is missing."}

    with open(SAMPLE_PLIST_PATH, "rb") as f:
        pl = plistlib.load(f)

    def bool_quirks(section: str) -> dict[str, bool]:
        quirks = pl.get(section, {}).get("Quirks", {}) if isinstance(pl.get(section), dict) else {}
        return {k: bool(v) for k, v in quirks.items() if isinstance(v, bool)}

    state = load_state()
    return {
        "success": True,
        "tag": state.get("opencore", {}).get("tag", "bundled"),
        "label": current_schema_label(state),
        "sections": [k for k in pl.keys() if not str(k).startswith("#")],
        "quirks": {
            "ACPI": bool_quirks("ACPI"),
            "Booter": bool_quirks("Booter"),
            "Kernel": bool_quirks("Kernel"),
            "UEFI": bool_quirks("UEFI"),
        },
    }


def _validate_sample_plist(raw: bytes) -> dict[str, Any]:
    try:
        pl = plistlib.loads(raw)
    except Exception as exc:
        return {"ok": False, "error": f"Downloaded Sample.plist is not valid Apple XML: {exc}"}
    if not isinstance(pl, dict):
        return {"ok": False, "error": "Downloaded Sample.plist is not a dictionary."}
    missing = [key for key in REQUIRED_SAMPLE_SECTIONS if key not in pl]
    if missing:
        return {"ok": False, "error": f"Sample.plist is missing required sections: {', '.join(missing)}"}
    return {"ok": True, "plist": pl}


def _validate_amd_patches(raw: bytes) -> dict[str, Any]:
    try:
        pl = plistlib.loads(raw)
    except Exception as exc:
        return {"ok": False, "error": f"Downloaded AMD patches.plist is not valid: {exc}"}
    patches = pl.get("Kernel", {}).get("Patch", []) if isinstance(pl, dict) else []
    if not isinstance(patches, list) or not patches:
        return {"ok": False, "error": "AMD patches.plist has no Kernel -> Patch entries."}
    return {"ok": True, "plist": pl, "patchCount": len(patches)}


def _schema_key_set(pl: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for section, value in pl.items():
        if str(section).startswith("#"):
            continue
        keys.add(str(section))
        if isinstance(value, dict):
            quirks = value.get("Quirks")
            if isinstance(quirks, dict):
                for qk in quirks:
                    keys.add(f"{section}.Quirks.{qk}")
    return keys


def _schema_diff(old_pl: dict[str, Any] | None, new_pl: dict[str, Any]) -> dict[str, list[str]]:
    old_keys = _schema_key_set(old_pl) if old_pl else set()
    new_keys = _schema_key_set(new_pl)
    return {
        "added": sorted(new_keys - old_keys),
        "removed": sorted(old_keys - new_keys),
    }


def _load_local_sample() -> dict[str, Any] | None:
    if not SAMPLE_PLIST_PATH.exists():
        return None
    with open(SAMPLE_PLIST_PATH, "rb") as f:
        return plistlib.load(f)


def _backup_file(path: Path, label: str) -> str | None:
    if not path.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = BACKUP_DIR / f"{path.name}.{label}.{stamp}"
    shutil.copy2(path, dest)
    backups = sorted(BACKUP_DIR.glob(f"{path.name}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in backups[MAX_BACKUPS:]:
        try:
            stale.unlink()
        except OSError:
            pass
    return dest.name


def fetch_opencore_releases(limit: int = 6) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{OPENCORE_REPO}/releases?per_page={limit}"
    payload = _github_json(url)
    releases = []
    for item in payload:
        if item.get("draft"):
            continue
        releases.append({
            "tag": item.get("tag_name", ""),
            "name": item.get("name") or item.get("tag_name", ""),
            "prerelease": bool(item.get("prerelease")),
            "publishedAt": item.get("published_at"),
            "notes": (item.get("body") or "").strip(),
            "htmlUrl": item.get("html_url"),
        })
    return releases


def fetch_sample_plist(tag: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{OPENCORE_REPO}/{tag}/Docs/Sample.plist"
    return _http_get(url)


def fetch_amd_vanilla() -> dict[str, Any]:
    meta = _github_json(f"https://api.github.com/repos/{AMD_VANILLA_REPO}/contents/patches.plist")
    download_url = meta.get("download_url") or f"https://raw.githubusercontent.com/{AMD_VANILLA_REPO}/master/patches.plist"
    raw = _http_get(download_url)
    return {
        "sha": meta.get("sha", ""),
        "htmlUrl": meta.get("html_url"),
        "raw": raw,
    }


def _unique_kext_repos(catalog: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for kext in catalog:
        repo = str(kext.get("github") or "").strip()
        if repo and repo not in seen:
            seen.append(repo)
    return seen


def _refresh_kext_versions(apply: bool) -> dict[str, Any]:
    catalog = load_kext_catalog()
    repos = _unique_kext_repos(catalog)
    repo_releases: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    for repo in repos:
        info = fetch_latest_release(repo)
        if not info or info.get("error"):
            errors.append(f"{repo}: {info.get('error') if info else 'no release'}")
            continue
        repo_releases[repo] = info

    updates = []
    unchanged = []
    for kext in catalog:
        repo = str(kext.get("github") or "").strip()
        current = str(kext.get("latestRelease") or kext.get("version") or "").strip()
        release = repo_releases.get(repo)
        if not release:
            continue
        latest = str(release.get("tag") or "").strip()
        entry = {
            "id": kext.get("id"),
            "name": kext.get("name"),
            "github": repo,
            "current": current or "unknown",
            "latest": latest,
            "downloadUrl": release.get("downloadUrl"),
            "publishedAt": release.get("publishedAt"),
        }
        if latest and latest != current:
            updates.append(entry)
            if apply:
                kext["latestRelease"] = latest
                kext["releasePublishedAt"] = release.get("publishedAt")
                if release.get("downloadUrl"):
                    kext["downloadUrl"] = release.get("downloadUrl")
        else:
            unchanged.append(entry)

    applied = 0
    if apply and updates:
        _backup_file(KEXTS_FILE, "kexts")
        with open(KEXTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["kexts"] = catalog
        data["lastUpdated"] = _now_iso()
        with open(KEXTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        applied = len(updates)

    return {
        "checkedRepos": len(repos),
        "updates": updates,
        "unchanged": unchanged,
        "errors": errors,
        "applied": applied,
    }


def check_updates() -> dict[str, Any]:
    """Query upstream without writing local files."""
    state = load_state()
    result: dict[str, Any] = {
        "success": True,
        "checkedAt": _now_iso(),
        "current": {
            "opencoreTag": state["opencore"].get("tag", "bundled"),
            "amdRef": state["amdVanilla"].get("ref", "bundled"),
            "sampleSha256": state["opencore"].get("sampleSha256") or _sha256_file(SAMPLE_PLIST_PATH),
            "label": current_schema_label(state),
            "canRollback": bool(state.get("canRollback")),
        },
        "available": {},
        "errors": [],
    }

    try:
        releases = fetch_opencore_releases()
        latest = next((r for r in releases if not r.get("prerelease")), releases[0] if releases else None)
        if not latest:
            raise RuntimeError("No OpenCorePkg releases found.")
        sample_raw = fetch_sample_plist(latest["tag"])
        validation = _validate_sample_plist(sample_raw)
        if not validation["ok"]:
            raise RuntimeError(validation["error"])
        local_sample = _load_local_sample()
        sample_sha = _sha256_bytes(sample_raw)
        local_sha = _sha256_file(SAMPLE_PLIST_PATH)
        if local_sha and local_sha == sample_sha and state["opencore"].get("tag") == "bundled":
            state["opencore"]["tag"] = latest["tag"]
            state["opencore"]["source"] = "matched-upstream"
            state["opencore"]["sampleSha256"] = local_sha
            save_state(state)
            result["current"]["opencoreTag"] = latest["tag"]
            result["current"]["label"] = current_schema_label(state)
        result["available"]["opencore"] = {
            "tag": latest["tag"],
            "publishedAt": latest.get("publishedAt"),
            "notes": latest.get("notes", ""),
            "htmlUrl": latest.get("htmlUrl"),
            "releases": releases,
            "changed": sample_sha != local_sha,
            "schemaDiff": _schema_diff(local_sample, validation["plist"]),
        }
    except Exception as exc:
        result["errors"].append(f"OpenCore: {exc}")
        result["available"]["opencore"] = {"error": str(exc)}

    try:
        amd = fetch_amd_vanilla()
        validation = _validate_amd_patches(amd["raw"])
        if not validation["ok"]:
            raise RuntimeError(validation["error"])
        amd_sha = _sha256_bytes(amd["raw"])
        result["available"]["amdVanilla"] = {
            "ref": amd.get("sha", "master")[:12],
            "htmlUrl": amd.get("htmlUrl"),
            "changed": amd_sha != _sha256_file(AMD_PATCHES_PATH),
            "patchCount": validation["patchCount"],
        }
    except Exception as exc:
        result["errors"].append(f"AMD Vanilla: {exc}")
        result["available"]["amdVanilla"] = {"error": str(exc)}

    try:
        kexts = _refresh_kext_versions(apply=False)
        result["available"]["kexts"] = kexts
    except Exception as exc:
        result["errors"].append(f"Kexts: {exc}")
        result["available"]["kexts"] = {"error": str(exc)}

    state["lastCheck"] = result["checkedAt"]
    save_state(state)
    result["current"]["canRollback"] = bool(state.get("canRollback"))
    result["success"] = True
    return result


def apply_updates(components: list[str] | None = None, opencore_tag: str | None = None) -> dict[str, Any]:
    """Download and replace selected upstream artifacts."""
    wanted = set(components or ["opencore", "amd", "kexts"])
    state = load_state()
    state["previous"] = {
        "opencore": dict(state.get("opencore") or {}),
        "amdVanilla": dict(state.get("amdVanilla") or {}),
        "kexts": dict(state.get("kexts") or {}),
    }
    applied: dict[str, Any] = {}
    errors: list[str] = []

    if "opencore" in wanted:
        try:
            tag = (opencore_tag or "").strip()
            if not tag:
                releases = fetch_opencore_releases(limit=1)
                if not releases:
                    raise RuntimeError("No OpenCorePkg releases found.")
                tag = releases[0]["tag"]
            raw = fetch_sample_plist(tag)
            validation = _validate_sample_plist(raw)
            if not validation["ok"]:
                raise RuntimeError(validation["error"])
            local_sample = _load_local_sample()
            backup = _backup_file(SAMPLE_PLIST_PATH, f"pre-{tag}")
            SAMPLE_PLIST_PATH.write_bytes(raw)
            state["opencore"] = {
                "tag": tag,
                "source": f"github:{OPENCORE_REPO}",
                "sampleSha256": _sha256_bytes(raw),
                "appliedAt": _now_iso(),
                "notes": "",
                "previousBackup": backup,
            }
            state["canRollback"] = True
            applied["opencore"] = {
                "tag": tag,
                "backup": backup,
                "schemaDiff": _schema_diff(local_sample, validation["plist"]),
            }
        except Exception as exc:
            errors.append(f"OpenCore: {exc}")

    if "amd" in wanted:
        try:
            amd = fetch_amd_vanilla()
            validation = _validate_amd_patches(amd["raw"])
            if not validation["ok"]:
                raise RuntimeError(validation["error"])
            backup = _backup_file(AMD_PATCHES_PATH, "pre-amd")
            AMD_PATCHES_PATH.write_bytes(amd["raw"])
            ref = amd.get("sha", "master")[:12]
            state["amdVanilla"] = {
                "ref": ref,
                "sha256": _sha256_bytes(amd["raw"]),
                "appliedAt": _now_iso(),
                "previousBackup": backup,
            }
            state["canRollback"] = True
            applied["amdVanilla"] = {
                "ref": ref,
                "backup": backup,
                "patchCount": validation["patchCount"],
            }
        except Exception as exc:
            errors.append(f"AMD Vanilla: {exc}")

    if "kexts" in wanted:
        try:
            kexts = _refresh_kext_versions(apply=True)
            state["kexts"]["lastChecked"] = _now_iso()
            if kexts.get("applied"):
                state["kexts"]["lastApplied"] = _now_iso()
                state["canRollback"] = True
            applied["kexts"] = kexts
        except Exception as exc:
            errors.append(f"Kexts: {exc}")

    save_state(state)
    return {
        "success": bool(applied),
        "applied": applied,
        "errors": errors,
        "current": {
            "opencoreTag": state["opencore"].get("tag", "bundled"),
            "amdRef": state["amdVanilla"].get("ref", "bundled"),
            "label": current_schema_label(state),
            "canRollback": bool(state.get("canRollback")),
        },
        "schema": get_sample_schema(),
    }


def rollback_updates() -> dict[str, Any]:
    """Restore the newest backup of Sample.plist, AMD patches, and kext catalog."""
    restored: list[str] = []
    missing: list[str] = []

    targets = [
        (SAMPLE_PLIST_PATH, "Sample.plist"),
        (AMD_PATCHES_PATH, "amd_patches.plist"),
        (KEXTS_FILE, "kexts.json"),
    ]
    for path, label in targets:
        backups = sorted(BACKUP_DIR.glob(f"{path.name}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not backups:
            missing.append(label)
            continue
        shutil.copy2(backups[0], path)
        restored.append(f"{label} <- {backups[0].name}")

    state = load_state()
    previous = state.get("previous") or {}
    if previous.get("opencore"):
        state["opencore"] = dict(previous["opencore"])
    else:
        state["opencore"]["tag"] = "bundled"
        state["opencore"]["source"] = "backup"
    if previous.get("amdVanilla"):
        state["amdVanilla"] = dict(previous["amdVanilla"])
    else:
        state["amdVanilla"]["ref"] = "bundled"
    state["opencore"]["sampleSha256"] = _sha256_file(SAMPLE_PLIST_PATH)
    state["amdVanilla"]["sha256"] = _sha256_file(AMD_PATCHES_PATH)
    state["canRollback"] = False
    save_state(state)

    return {
        "success": bool(restored),
        "restored": restored,
        "missing": missing,
        "current": {
            "opencoreTag": state["opencore"].get("tag"),
            "label": current_schema_label(state),
            "canRollback": False,
        },
        "schema": get_sample_schema(),
    }


def local_status() -> dict[str, Any]:
    state = load_state()
    return {
        "success": True,
        "current": {
            "opencoreTag": state["opencore"].get("tag", "bundled"),
            "amdRef": state["amdVanilla"].get("ref", "bundled"),
            "appliedAt": state["opencore"].get("appliedAt"),
            "lastCheck": state.get("lastCheck"),
            "label": current_schema_label(state),
            "canRollback": bool(state.get("canRollback")),
        },
        "schema": get_sample_schema(),
    }
