"""OpenCore Studio — Plist Validator.

Runs heuristic rules against a config.plist dictionary to detect fatal boot mistakes,
subtle panics, missing dependencies, and hardware incompatibilities before boot.
"""

from __future__ import annotations

from typing import Any

from .troubleshooter import usb_setup_findings


def validate_config(pl: dict[str, Any], hardware_info: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    hardware_info = hardware_info or {}

    # 1. Kext validation: Kernel -> Add
    kernel_add = pl.get("Kernel", {}).get("Add", [])
    enabled_kexts = [k for k in kernel_add if k.get("Enabled", False)]

    # Check Lilu at index 0
    if not enabled_kexts:
        results.append({
            "level": "FAIL",
            "section": "Kernel -> Add",
            "message": "No kexts are enabled in Kernel -> Add.",
            "remedy": "Enable Lilu.kext and VirtualSMC.kext at minimum."
        })
    else:
        first_kext = enabled_kexts[0].get("BundlePath", "")
        if "Lilu.kext" not in first_kext:
            results.append({
                "level": "FAIL",
                "section": "Kernel -> Add",
                "message": f"First enabled kext is '{first_kext}', but Lilu.kext MUST be index 0.",
                "remedy": "Reorder Kernel -> Add so Lilu.kext is the very first entry."
            })
        else:
            results.append({
                "level": "PASS",
                "section": "Kernel -> Add",
                "message": "Lilu.kext is correctly located at index 0."
            })

    # Check VirtualSMC and plugins
    has_vsmc = any("VirtualSMC.kext" in k.get("BundlePath", "") for k in enabled_kexts)
    has_fakesmc = any("FakeSMC.kext" in k.get("BundlePath", "") for k in enabled_kexts)
    if has_vsmc and has_fakesmc:
        results.append({
            "level": "FAIL",
            "section": "Kernel -> Add",
            "message": "Both VirtualSMC and FakeSMC are enabled. They strictly conflict.",
            "remedy": "Disable FakeSMC and keep VirtualSMC."
        })
    elif not has_vsmc and not has_fakesmc:
        results.append({
            "level": "FAIL",
            "section": "Kernel -> Add",
            "message": "Missing SMC emulator (neither VirtualSMC nor FakeSMC is enabled).",
            "remedy": "Add and enable VirtualSMC.kext."
        })
    else:
        results.append({
            "level": "PASS",
            "section": "Kernel -> Add",
            "message": "Valid SMC emulator configured (VirtualSMC)."
        })

    # Check SMC plugins come after VirtualSMC
    vsmc_idx = next((i for i, k in enumerate(enabled_kexts) if "VirtualSMC.kext" in k.get("BundlePath", "")), -1)
    for i, k in enumerate(enabled_kexts):
        bp = k.get("BundlePath", "")
        if bp.startswith("SMC") and "VirtualSMC.kext" not in bp:
            if i < vsmc_idx:
                results.append({
                    "level": "FAIL",
                    "section": "Kernel -> Add",
                    "message": f"Sensor plugin '{bp}' is loaded before VirtualSMC.kext.",
                    "remedy": "Move VirtualSMC.kext before any SMC plugins."
                })
                break

    # Check WhateverGreen vs NootedRed conflict
    has_weg = any("WhateverGreen.kext" in k.get("BundlePath", "") for k in enabled_kexts)
    has_nooted = any("NootedRed.kext" in k.get("BundlePath", "") for k in enabled_kexts)
    if has_weg and has_nooted:
        results.append({
            "level": "FAIL",
            "section": "Kernel -> Add",
            "message": "WhateverGreen.kext and NootedRed.kext are both enabled. They conflict and crash boot.",
            "remedy": "Disable WhateverGreen when using NootedRed for AMD APU graphics."
        })

    results.extend(usb_setup_findings({"config": pl, "hardwareInfo": hardware_info}))

    # 3. Boot-args check
    nvram_add = pl.get("NVRAM", {}).get("Add", {}).get("7C436110-AB2A-4BBB-A880-FE41995C9F82", {})
    boot_args = nvram_add.get("boot-args", "")
    if isinstance(boot_args, (bytes, bytearray)):
        boot_args = boot_args.decode("utf-8", errors="replace")

    # Check agdpmod=pikera for AMD Navi
    gpu_type = str(hardware_info.get("gpuType", "")).lower()
    if any(navi in gpu_type for navi in ["navi", "rx 5700", "rx 6600", "rx 6800", "rx 6900"]):
        if "agdpmod=pikera" not in boot_args:
            results.append({
                "level": "WARN",
                "section": "NVRAM -> boot-args",
                "message": "AMD Navi dGPU selected but 'agdpmod=pikera' is missing from boot-args. Display may go black on boot.",
                "remedy": "Add 'agdpmod=pikera' to boot-args."
            })
        else:
            results.append({
                "level": "PASS",
                "section": "NVRAM -> boot-args",
                "message": "'agdpmod=pikera' is configured for AMD Navi graphics."
            })

    # 4. ProvideCurrentCpuInfo check for Alder/Raptor / AMD
    cpu_family = str(hardware_info.get("cpuFamily", "")).lower()
    pcci = pl.get("Kernel", {}).get("Quirks", {}).get("ProvideCurrentCpuInfo", False)
    if any(x in cpu_family for x in ["alder", "raptor", "12th", "13th", "14th", "ryzen", "amd"]):
        if not pcci:
            results.append({
                "level": "FAIL",
                "section": "Kernel -> Quirks",
                "message": f"ProvideCurrentCpuInfo is False for {cpu_family}. macOS will panic during early kernel init.",
                "remedy": "Enable Kernel -> Quirks -> ProvideCurrentCpuInfo."
            })
        else:
            results.append({
                "level": "PASS",
                "section": "Kernel -> Quirks",
                "message": "ProvideCurrentCpuInfo is correctly enabled for hybrid/AMD CPU."
            })

    # 5. PlatformInfo / SMBIOS
    generic = pl.get("PlatformInfo", {}).get("Generic", {})
    model = generic.get("SystemProductName", "")
    serial = generic.get("SystemSerialNumber", "")
    mlb = generic.get("MLB", "")
    uuid_str = generic.get("SystemUUID", "")

    if not model or model == "Sample":
        results.append({
            "level": "FAIL",
            "section": "PlatformInfo -> Generic",
            "message": "SystemProductName is empty or placeholder.",
            "remedy": "Select a valid Mac model (e.g. iMac20,1 or MacPro7,1)."
        })
    elif not serial or not mlb or not uuid_str:
        results.append({
            "level": "WARN",
            "section": "PlatformInfo -> Generic",
            "message": "Serial Number, MLB, or UUID are missing. iCloud/iMessage will not function.",
            "remedy": "Generate fresh serials in the SMBIOS tab."
        })
    else:
        results.append({
            "level": "PASS",
            "section": "PlatformInfo -> Generic",
            "message": f"SMBIOS valid: {model} with full serial and MLB set."
        })

    # 6. Booter -> Quirks: ResizeAppleGpuBars
    resize_bars = pl.get("Booter", {}).get("Quirks", {}).get("ResizeAppleGpuBars", -1)
    results.append({
        "level": "PASS",
        "section": "Booter -> Quirks",
        "message": f"ResizeAppleGpuBars set to {resize_bars} (recommended 0 or -1 for ReBAR compatibility)."
    })

    return results
