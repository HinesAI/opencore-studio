"""OpenCore Studio — AMD Vanilla Kernel Patch Injector.

Loads and customizes official AMD Vanilla patches for 15h, 16h, 17h, and 19h AMD CPUs,
automatically computing physical core count hex substitutions.
"""

from __future__ import annotations

import plistlib
from pathlib import Path
from typing import Any

from .paths import mutable_file

AMD_PATCHES_FILE = mutable_file("amd_patches.plist")


def get_amd_patches(core_count: int = 8) -> list[dict[str, Any]]:
    """Loads official AMD Vanilla kernel patches and injects the physical core count."""
    if not AMD_PATCHES_FILE.exists():
        return []

    with open(AMD_PATCHES_FILE, "rb") as f:
        pl = plistlib.load(f)

    patches = pl.get("Kernel", {}).get("Patch", [])
    customized = []

    core_byte = max(1, min(128, int(core_count)))

    for p in patches:
        patch_copy = dict(p)
        comment = patch_copy.get("Comment", "")
        if "Force cpuid_cores_per_package" in comment:
            old_replace = patch_copy.get("Replace", b"")
            if isinstance(old_replace, (bytes, bytearray)) and len(old_replace) >= 2:
                # Replace the second byte with the physical core count byte
                new_replace = bytearray(old_replace)
                new_replace[1] = core_byte
                patch_copy["Replace"] = bytes(new_replace)
        customized.append(patch_copy)

    return customized
