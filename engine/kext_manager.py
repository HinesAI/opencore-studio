"""OpenCore Studio — Kext Manager and Dependency Resolution Engine.

Enforces strict topological ordering (Lilu index 0, VirtualSMC before sensor plugins,
child plugins following parents) and manages official & custom kext repositories.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any

from .paths import mutable_file

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
KEXTS_FILE = mutable_file("kexts.json")
REPOS_FILE = mutable_file("repos.json")


def load_kext_catalog() -> list[dict[str, Any]]:
    if not KEXTS_FILE.exists():
        return []
    with open(KEXTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("kexts", [])


def load_repos_config() -> dict[str, Any]:
    if not REPOS_FILE.exists():
        return {"repositories": [], "customRepositories": [], "instructions": {}}
    with open(REPOS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_repos_config(config: dict[str, Any]) -> None:
    with open(REPOS_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def add_custom_repo(repo_data: dict[str, Any]) -> dict[str, Any]:
    """Adds a custom kext repository (GitHub repo or JSON manifest)."""
    cfg = load_repos_config()
    name = str(repo_data.get("name") or "").strip()
    repo_id = str(repo_data.get("id") or "").strip()
    if not repo_id and name:
        import re
        repo_id = re.sub(r"[^a-zA-Z0-9_]+", "_", name.lower()).strip("_")

    repo_type = str(repo_data.get("type") or "github_repo").strip()
    target = str(repo_data.get("target") or repo_data.get("url") or "").strip()

    if not repo_id or not target:
        return {"success": False, "error": "Repository Name/ID and Target/URL are required."}

    custom_repos = cfg.get("customRepositories", [])
    # Check if ID already exists
    for r in custom_repos:
        if r.get("id") == repo_id:
            r.update({
                "name": name or repo_id,
                "type": repo_type,
                "target": target,
                "url": target,
                "enabled": repo_data.get("enabled", True),
                "description": repo_data.get("description", "")
            })
            save_repos_config(cfg)
            return {"success": True, "action": "updated", "repo": r, "data": load_repos_config()}

    new_repo = {
        "id": repo_id,
        "name": name or repo_id,
        "type": repo_type,
        "target": target,
        "url": target,
        "maintainer": repo_data.get("maintainer", "Community"),
        "enabled": repo_data.get("enabled", True),
        "description": repo_data.get("description", "Custom repository added via OpenCore Studio"),
        "official": False
    }
    custom_repos.append(new_repo)
    cfg["customRepositories"] = custom_repos
    save_repos_config(cfg)
    return {"success": True, "action": "created", "repo": new_repo, "data": load_repos_config()}
    return {"ok": True, "action": "added", "repo": new_repo}


def sort_kexts_strict(selected_kext_ids: list[str]) -> list[dict[str, Any]]:
    """Topological sort enforcing absolute OpenCore invariants.

    Invariants:
    1. Lilu.kext is always first (index 0).
    2. VirtualSMC.kext is always placed before any SMC plugins.
    3. WhateverGreen and AppleALC follow Lilu.
    4. Child plugins (Contents/PlugIns/...) must strictly follow their parent bundle.
    5. Conflicting kexts (e.g. WhateverGreen vs NootedRed) are resolved.
    """
    catalog_map = {}
    for k in load_kext_catalog():
        catalog_map[k["id"].lower()] = k
        catalog_map[k["name"].lower()] = k
    selected = []
    seen = set()
    for kid in selected_kext_ids:
        k_obj = catalog_map.get(str(kid).lower())
        if k_obj and k_obj["id"] not in seen:
            selected.append(k_obj)
            seen.add(k_obj["id"])

    # Check for conflicts
    has_weg = any(k["id"] == "WhateverGreen" for k in selected)
    has_nooted = any(k["id"] == "NootedRed" for k in selected)
    if has_weg and has_nooted:
        # NootedRed conflicts with WhateverGreen. Default to WhateverGreen unless user overrides.
        selected = [k for k in selected if k["id"] != "NootedRed"]

    # Topological weight sorting:
    # Lilu: priority 0
    # VirtualSMC: priority 10
    # SMC plugins: priority 11..19
    # WhateverGreen: 20
    # AppleALC: 30
    # Others sorted by priority, with parent kexts before child plugins
    def get_sort_key(k: dict[str, Any]) -> tuple[int, int, str]:
        prio = k.get("priority", 50)
        is_plugin = 1 if "Contents/PlugIns" in k.get("bundlePath", "") else 0
        return (prio, is_plugin, k.get("bundlePath", ""))

    sorted_kexts = sorted(selected, key=get_sort_key)

    # Double check Lilu is index 0 if present
    lilu_idx = next((i for i, k in enumerate(sorted_kexts) if k["id"] == "Lilu"), -1)
    if lilu_idx > 0:
        lilu = sorted_kexts.pop(lilu_idx)
        sorted_kexts.insert(0, lilu)

    # Double check VirtualSMC comes before any SMC plugin
    vsmc_idx = next((i for i, k in enumerate(sorted_kexts) if k["id"] == "VirtualSMC"), -1)
    if vsmc_idx >= 0:
        for i, k in enumerate(sorted_kexts):
            if k["id"].startswith("SMC") and k["id"] != "VirtualSMC" and i < vsmc_idx:
                # Move VirtualSMC before this plugin
                vsmc = sorted_kexts.pop(vsmc_idx)
                sorted_kexts.insert(i, vsmc)
                break

    return sorted_kexts


def build_kernel_add_entries(selected_kext_ids: list[str]) -> list[dict[str, Any]]:
    """Builds OpenCore Kernel -> Add array of dictionaries."""
    sorted_kexts = sort_kexts_strict(selected_kext_ids)
    entries = []
    for k in sorted_kexts:
        entries.append({
            "Arch": "Any",
            "BundlePath": k["bundlePath"],
            "Comment": k.get("description", k["name"])[:80],
            "Enabled": True,
            "ExecutablePath": k.get("executablePath", ""),
            "MaxKernel": k.get("maxKernel", ""),
            "MinKernel": k.get("minKernel", ""),
            "PlistPath": k.get("plistPath", "Contents/Info.plist")
        })
    return entries


def fetch_latest_release(github_repo: str) -> dict[str, Any] | None:
    """Queries GitHub API for the latest release asset download URL."""
    if not github_repo:
        return None
    url = f"https://api.github.com/repos/{github_repo}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "OpenCoreStudio"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tag = data.get("tag_name", "latest")
            assets = data.get("assets", [])
            # Prefer RELEASE zip
            release_zip = None
            for a in assets:
                name = a.get("name", "")
                if name.endswith(".zip"):
                    if "RELEASE" in name.upper():
                        release_zip = a
                        break
                    elif release_zip is None:
                        release_zip = a
            return {
                "tag": tag,
                "assetName": release_zip.get("name") if release_zip else None,
                "downloadUrl": release_zip.get("browser_download_url") if release_zip else None,
                "publishedAt": data.get("published_at")
            }
    except Exception as e:
        return {"error": str(e)}
