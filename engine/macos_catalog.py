"""Universal macOS full-installer catalog (Monterey and newer).

Reads Apple's public sucatalog so every machine sees the same list.
softwareupdate is only used to badge what this Mac can fetch locally.
Nothing is downloaded except catalog/dist metadata.
"""

from __future__ import annotations

import gzip
import json
import plistlib
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import cache_dir

CACHE_DIR = cache_dir()
CACHE_PATH = CACHE_DIR / "macos-catalog.json"
DIST_DIR = CACHE_DIR / "macos-dists"
CACHE_SECONDS = 3600
MIN_VERSION = (12, 0)
USER_AGENT = "OpenCoreStudio-macOSCatalog/1.0"
CATALOG_SOURCE = "apple-sucatalog"

CATALOG_URLS = [
    "https://swscan.apple.com/content/catalogs/others/index-26-15-14-13-12-10.16-10.15-10.14-10.13-10.12-10.11-10.10-10.9-mountainlion-lion-snowleopard-leopard.merged-1.sucatalog",
    "https://swscan.apple.com/content/catalogs/others/index-15-14-13-12-10.16-10.15-10.14-10.13-10.12-10.11-10.10-10.9-mountainlion-lion-snowleopard-leopard.merged-1.sucatalog",
]

LINE_RE = re.compile(
    r"Title:\s*(?P<title>[^,]+),\s*Version:\s*(?P<version>[\d.]+),\s*"
    r"Size:\s*(?P<size>\d+)\s*(?P<unit>KiB|MiB|GiB|Bytes)?,\s*"
    r"Build:\s*(?P<build>[^,]+?)(?:,\s*Deferred:\s*(?P<deferred>\S+))?\s*$",
    re.IGNORECASE,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_version(raw: str) -> tuple[int, ...]:
    parts = []
    for bit in str(raw).split("."):
        try:
            parts.append(int(bit))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def _version_ok(raw: str) -> bool:
    ver = _parse_version(raw)
    padded = (ver + (0, 0))[:2]
    return padded >= MIN_VERSION


def _size_label(nbytes: int) -> str:
    return f"{nbytes / (1024 ** 3):.1f} GB"


def _major_name(title: str, version: str) -> str:
    cleaned = title.replace("macOS ", "").strip()
    if cleaned:
        return cleaned
    return {
        12: "Monterey",
        13: "Ventura",
        14: "Sonoma",
        15: "Sequoia",
        26: "Tahoe",
    }.get(_parse_version(version)[0], f"macOS {_parse_version(version)[0]}")


def _http_get(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def _load_cache() -> dict[str, Any] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if data.get("source") != CATALOG_SOURCE:
            return None
        fetched = datetime.fromisoformat(data.get("fetchedAt", ""))
        if (_now() - fetched).total_seconds() < CACHE_SECONDS:
            return data
    except Exception:
        return None
    return None


def _save_cache(data: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _softwareupdate_local() -> list[dict[str, str]]:
    try:
        proc = subprocess.run(
            ["softwareupdate", "--list-full-installers"],
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    found = []
    for line in text.splitlines():
        match = LINE_RE.search(line.strip().lstrip("* "))
        if not match:
            continue
        found.append({
            "version": match.group("version").strip(),
            "build": match.group("build").strip(),
        })
    return found


def _fetch_catalog() -> tuple[dict[str, Any], str]:
    last_error = "No sucatalog URL succeeded."
    for url in CATALOG_URLS:
        try:
            raw = _http_get(url, timeout=45)
            data = plistlib.loads(raw)
            if data.get("Products"):
                return data, url
        except Exception as exc:
            last_error = str(exc)
            continue
    raise RuntimeError(last_error)


def _dist_text(product_id: str, dist_url: str) -> str:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    cache = DIST_DIR / f"{product_id}.xml"
    if cache.exists() and cache.stat().st_size > 0:
        return cache.read_text(encoding="utf-8", errors="replace")
    text = _http_get(dist_url, timeout=20).decode("utf-8", errors="replace")
    cache.write_text(text, encoding="utf-8")
    return text


def _parse_dist(xml: str) -> dict[str, str]:
    title_m = re.search(r"<title>([^<]+)</title>", xml, re.I)
    version_m = re.search(r"<key>VERSION</key>\s*<string>([^<]+)</string>", xml)
    build_m = re.search(r"<key>BUILD</key>\s*<string>([^<]+)</string>", xml)
    return {
        "title": (title_m.group(1).strip() if title_m else ""),
        "version": (version_m.group(1).strip() if version_m else ""),
        "build": (build_m.group(1).strip() if build_m else ""),
    }


def _catalog_installers() -> tuple[list[dict[str, Any]], str]:
    catalog, catalog_url = _fetch_catalog()
    installers: list[dict[str, Any]] = []
    for product_id, product in (catalog.get("Products") or {}).items():
        packages = product.get("Packages") or []
        ia_pkgs = [p for p in packages if "InstallAssistant.pkg" in str(p.get("URL") or "")]
        if not ia_pkgs:
            continue
        dists = product.get("Distributions") or {}
        dist_url = dists.get("English") or dists.get("en") or ""
        if not dist_url:
            continue
        meta = _parse_dist(_dist_text(str(product_id), dist_url))
        version = meta.get("version") or ""
        if not version or not _version_ok(version):
            continue
        title = meta.get("title") or f"macOS {version}"
        size = int(ia_pkgs[0].get("Size") or 0)
        post = product.get("PostDate")
        installers.append({
            "id": f"{version}-{meta.get('build') or product_id}",
            "productId": str(product_id),
            "title": title,
            "name": _major_name(title, version),
            "version": version,
            "build": meta.get("build") or "",
            "sizeBytes": size,
            "sizeLabel": _size_label(size) if size else "unknown",
            "postedAt": post.isoformat() if hasattr(post, "isoformat") else str(post or ""),
            "pkgUrl": ia_pkgs[0].get("URL") or "",
            "source": "sucatalog",
            "availableOnThisMac": False,
        })
    installers.sort(key=lambda item: _parse_version(item["version"]), reverse=True)
    return installers, catalog_url


def _latest_per_major(installers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep only the newest version of each macOS name (Tahoe, Sequoia, …)."""
    best: dict[str, dict[str, Any]] = {}
    for item in installers:
        key = item.get("name") or f"macOS {_parse_version(item.get('version') or '0')[0]}"
        current = best.get(key)
        if not current:
            best[key] = item
            continue
        item_ver = _parse_version(item.get("version") or "0")
        cur_ver = _parse_version(current.get("version") or "0")
        newer = item_ver > cur_ver or (
            item_ver == cur_ver and (item.get("postedAt") or "") > (current.get("postedAt") or "")
        )
        if newer:
            best[key] = item
    latest = sorted(best.values(), key=lambda item: _parse_version(item.get("version") or "0"), reverse=True)
    return latest, max(len(installers) - len(latest), 0)


def _collapse_to_latest(payload: dict[str, Any]) -> dict[str, Any]:
    latest, hidden = _latest_per_major(list(payload.get("installers") or []))
    payload["installers"] = latest
    majors = []
    for item in latest:
        if item.get("name") and item["name"] not in majors:
            majors.append(item["name"])
    payload["majors"] = majors
    payload["localCount"] = sum(1 for item in latest if item.get("availableOnThisMac"))
    payload["olderReleasesHidden"] = hidden
    return payload


def _with_downloads(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from .macos_downloader import attach_local_downloads
        return attach_local_downloads(payload)
    except Exception:
        payload.setdefault("downloadedCount", 0)
        return payload


def list_macos_installers(refresh: bool = False) -> dict[str, Any]:
    """Same Monterey+ catalog on every machine; badge local softwareupdate hits."""
    if not refresh:
        cached = _load_cache()
        if cached:
            cached["cached"] = True
            cached["success"] = True
            return _with_downloads(_collapse_to_latest(cached))

    error = None
    installers: list[dict[str, Any]] = []
    catalog_url = ""
    try:
        installers, catalog_url = _catalog_installers()
    except Exception as exc:
        error = str(exc)

    local = _softwareupdate_local()
    local_keys = {(i["version"], i["build"]) for i in local}
    for item in installers:
        item["availableOnThisMac"] = (item.get("version"), item.get("build")) in local_keys

    majors = []
    for item in installers:
        if item["name"] not in majors:
            majors.append(item["name"])

    payload = {
        "success": bool(installers),
        "cached": False,
        "fetchedAt": _now().replace(microsecond=0).isoformat(),
        "minimumVersion": "12.0",
        "minimumName": "Monterey",
        "source": CATALOG_SOURCE,
        "catalogUrl": catalog_url,
        "note": (
            "This list is Apple’s public full-installer catalog (same on every Mac). "
            "The badge marks versions softwareupdate can fetch on this machine. "
            "Download only the newest build of each macOS; the pkg is cached for later USB builds."
        ),
        "majors": majors,
        "localCount": sum(1 for i in installers if i.get("availableOnThisMac")),
        "installers": installers,
        "error": error if not installers else None,
    }
    if installers:
        _save_cache(payload)
    return _with_downloads(_collapse_to_latest(payload))
