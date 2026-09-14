"""CPU and GPU catalog matching for OpenCore Studio.

Maps user-typed models (W-2133, i7-10700K, RX 6800 XT) onto architecture
profiles, recommended kexts, and optional/required boot-args.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .profiles import get_profile, list_profiles

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
CPU_CATALOG = DATA_DIR / "cpu_catalog.json"
GPU_CATALOG = DATA_DIR / "gpus.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cpu_catalog() -> dict[str, Any]:
    return _load_json(CPU_CATALOG)


def load_gpu_catalog() -> dict[str, Any]:
    data = _load_json(GPU_CATALOG)
    return data if data else {"gpus": []}


def list_gpus() -> list[dict[str, Any]]:
    return list(load_gpu_catalog().get("gpus") or [])


def get_gpu(gpu_id: str) -> dict[str, Any] | None:
    target = str(gpu_id or "").strip().lower()
    for gpu in list_gpus():
        if str(gpu.get("id", "")).lower() == target:
            return gpu
    return None


def normalize_cpu_query(raw: str) -> str:
    """Turn 'AMD Ryzen 5 3400GE' / 'i7-10700K' into a compact SKU (3400GE, I7-10700K)."""
    text = str(raw or "").strip().upper().replace("®", "").replace("™", "")
    text = re.sub(r"[,()/]", " ", text)

    ryzen = re.search(
        r"\b(?:AMD\s+)?(?:RYZEN\s+)?R?([3579])\s*-?\s*([0-9]{4}[A-Z]{0,3})\b",
        text,
    )
    if ryzen:
        return ryzen.group(2)

    intel = re.search(r"\b(I[3579])[-\s]?([0-9]{3,5}[A-Z]{0,3})\b", text)
    if intel:
        return f"{intel.group(1)}-{intel.group(2)}"

    xeon_w = re.search(r"\bW[-\s]?([0-9]{4}[A-Z]*)\b", text)
    if xeon_w:
        return f"W-{xeon_w.group(1)}"

    ultra = re.search(r"\bULTRA\s*([579])\s*-?\s*([0-9]{3}[A-Z]*)\b", text)
    if ultra:
        return f"ULTRA{ultra.group(1)}-{ultra.group(2)}"

    text = re.sub(r"\b(INTEL|AMD|XEON|CORE|RYZEN|THREADRIPPER|PROCESSOR|CPU)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip().replace(" ", "")
    text = re.sub(r"^(W)([0-9]{4}[A-Z]*)$", r"\1-\2", text)
    text = re.sub(r"^(I[3579])([0-9]{3,5}[A-Z]*)$", r"\1-\2", text)
    return text


_PROFILE_GPU = {
    "amd_apu_nooted": "amd_apu",
    "intel_haswell": "intel_hd_5x00",
    "intel_skylake": "intel_hd_5x00",
    "intel_kaby_lake": "intel_uhd_630",
    "intel_coffee_lake": "intel_uhd_630",
    "intel_comet_lake": "intel_uhd_630",
    "intel_alder_raptor": "intel_uhd_7x0",
    "intel_meteor_lake": "intel_uhd_7x0",
}


def _suggested_gpu(profile_id: str, extra: str | None = None) -> str:
    return extra or _PROFILE_GPU.get(profile_id, "")


def _profile_summary(profile_id: str) -> dict[str, Any] | None:
    profile = get_profile(profile_id)
    if not profile:
        return None
    return {
        "id": profile.get("id", profile_id),
        "name": profile.get("name", profile_id),
        "cpuFamily": profile.get("cpuFamily", ""),
        "chipsets": profile.get("chipsets", []),
        "description": profile.get("description", ""),
        "examples": profile.get("examples", []),
        "recommendedSmbios": profile.get("recommendedSmbios"),
    }


def match_cpu(query: str) -> dict[str, Any]:
    """Resolve a typed CPU model to one architecture profile."""
    original = str(query or "").strip()
    if not original:
        return {"success": False, "error": "Type a CPU model, e.g. W-2133 or i7-10700K."}

    catalog = load_cpu_catalog()
    needle = normalize_cpu_query(original)
    raw_upper = original.upper()

    for model in catalog.get("models") or []:
        aliases = [model.get("id", "")] + list(model.get("aliases") or [])
        normalized_aliases = {normalize_cpu_query(a) for a in aliases if a}
        if needle in normalized_aliases or raw_upper == str(model.get("id", "")).upper():
            summary = _profile_summary(model["profileId"])
            return {
                "success": True,
                "query": original,
                "normalized": needle,
                "matchType": "model",
                "cpu": model,
                "profile": summary,
                "suggestedGpuId": _suggested_gpu(model["profileId"], model.get("suggestedGpuId")),
            }

    for rule in catalog.get("rules") or []:
        pattern = rule.get("pattern") or ""
        try:
            if re.search(pattern, needle, re.IGNORECASE) or re.search(pattern, raw_upper, re.IGNORECASE):
                summary = _profile_summary(rule["profileId"])
                return {
                    "success": True,
                    "query": original,
                    "normalized": needle,
                    "matchType": "rule",
                    "rule": rule.get("label") or pattern,
                    "profile": summary,
                    "suggestedGpuId": _suggested_gpu(rule["profileId"], rule.get("suggestedGpuId")),
                }
        except re.error:
            continue

    # Last resort: scan profile names / examples / search terms
    lowered = original.lower()
    for profile in list_profiles():
        hay = " ".join([
            str(profile.get("id", "")),
            str(profile.get("name", "")),
            str(profile.get("cpuFamily", "")),
            " ".join(profile.get("examples") or []),
            " ".join(profile.get("searchTerms") or []),
        ]).lower()
        if lowered in hay:
            return {
                "success": True,
                "query": original,
                "normalized": needle,
                "matchType": "profile-text",
                "profile": profile,
                "suggestedGpuId": _suggested_gpu(str(profile.get("id") or "")),
            }

    return {
        "success": False,
        "query": original,
        "normalized": needle,
        "error": f"No OpenCore architecture profile matches '{original}'.",
    }


def match_gpu(query: str) -> dict[str, Any]:
    original = str(query or "").strip()
    if not original:
        return {"success": False, "error": "Type a GPU, e.g. RX 6800 XT or UHD 630."}
    lowered = original.lower().replace("radeon", " ").replace("geforce", " ")
    lowered = re.sub(r"\s+", " ", lowered).strip()

    hits = []
    for gpu in list_gpus():
        aliases = [gpu.get("id", ""), gpu.get("name", ""), gpu.get("family", "")]
        aliases.extend(gpu.get("examples") or [])
        aliases.extend(gpu.get("aliases") or [])
        blob = " ".join(str(a) for a in aliases).lower()
        if lowered in blob or any(str(a).lower() == lowered for a in aliases):
            hits.append(gpu)
            continue
        compact = lowered.replace(" ", "")
        if compact and compact in blob.replace(" ", ""):
            hits.append(gpu)

    if not hits:
        return {"success": False, "query": original, "error": f"No GPU family matches '{original}'."}
    return {"success": True, "query": original, "gpus": hits, "gpu": hits[0]}


def gpu_apply_plan(gpu_id: str) -> dict[str, Any]:
    """Return boot-arg / kext changes a GPU family should offer or apply."""
    gpu = get_gpu(gpu_id)
    if not gpu:
        return {"success": False, "error": f"Unknown GPU '{gpu_id}'."}
    required_args = [a["arg"] for a in gpu.get("bootArgs") or [] if a.get("required")]
    optional_args = [a for a in gpu.get("bootArgs") or [] if not a.get("required")]
    return {
        "success": True,
        "gpu": gpu,
        "requiredBootArgs": required_args,
        "optionalBootArgs": optional_args,
        "addKexts": list(gpu.get("kexts") or []),
        "removeKexts": list(gpu.get("avoidKexts") or []),
        "support": gpu.get("support", "unknown"),
        "notes": gpu.get("notes", ""),
    }
