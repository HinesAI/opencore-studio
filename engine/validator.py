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

    results.extend(_hedt_dortania_findings(pl, hardware_info))
    return results


def _hedt_dortania_findings(pl: dict[str, Any], hardware_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Haswell-E / Broadwell-E / X99 required Dortania keys that used to ship blank."""
    profile_id = str(hardware_info.get("profileId") or "").lower()
    cpu_family = str(hardware_info.get("cpuFamily") or "").lower()
    blob = f"{profile_id} {cpu_family}"
    if not any(token in blob for token in ("haswell_e", "haswell-e", "broadwell_e", "broadwell-e", "x99", "c612")):
        return []

    results: list[dict[str, Any]] = []
    emulate = (pl.get("Kernel") or {}).get("Emulate") or {}
    cpuid = emulate.get("Cpuid1Data") or b""
    mask = emulate.get("Cpuid1Mask") or b""
    if isinstance(cpuid, str):
        cpuid = cpuid.encode()
    if isinstance(mask, str):
        mask = mask.encode()
    if not cpuid or not mask:
        results.append({
            "level": "FAIL",
            "section": "Kernel -> Emulate",
            "message": "Cpuid1Data / Cpuid1Mask are empty. Haswell-E and Broadwell-E have no native XCPM; Dortania requires the CPUID spoof or the kernel handoff dies at EXITBS:START.",
            "remedy": "Haswell-E/EP (v3): Cpuid1Data C3060300… with mask FFFFFFFF…. Broadwell-E/EP (v4): D4060300… with the same mask."
        })
    else:
        results.append({
            "level": "PASS",
            "section": "Kernel -> Emulate",
            "message": "CPUID spoof is present for X99/C612 XCPM."
        })

    quirks = (pl.get("Kernel") or {}).get("Quirks") or {}
    if not quirks.get("AppleXcpmExtraMsrs"):
        results.append({
            "level": "FAIL",
            "section": "Kernel -> Quirks",
            "message": "AppleXcpmExtraMsrs is disabled. Dortania requires it for Broadwell-E and older Xeons.",
            "remedy": "Enable Kernel -> Quirks -> AppleXcpmExtraMsrs."
        })
    if not quirks.get("PowerTimeoutKernelPanic"):
        results.append({
            "level": "FAIL",
            "section": "Kernel -> Quirks",
            "message": "PowerTimeoutKernelPanic is disabled. Dortania enables this on Haswell-E / Broadwell-E.",
            "remedy": "Enable Kernel -> Quirks -> PowerTimeoutKernelPanic."
        })

    if not ((pl.get("UEFI") or {}).get("Quirks") or {}).get("IgnoreInvalidFlexRatio"):
        results.append({
            "level": "FAIL",
            "section": "UEFI -> Quirks",
            "message": "IgnoreInvalidFlexRatio is disabled. Dortania requires it on all pre-Skylake firmware.",
            "remedy": "Enable UEFI -> Quirks -> IgnoreInvalidFlexRatio."
        })
    else:
        results.append({
            "level": "PASS",
            "section": "UEFI -> Quirks",
            "message": "IgnoreInvalidFlexRatio is enabled for this pre-Skylake platform."
        })

    ssdt_paths = {
        str(entry.get("Path") or "").upper()
        for entry in ((pl.get("ACPI") or {}).get("Add") or [])
        if entry.get("Enabled", True)
    }
    acpi_patches = [
        entry for entry in ((pl.get("ACPI") or {}).get("Patch") or [])
        if entry.get("Enabled", True)
    ]
    xcrs = any(
        "xcrs" in str(entry.get("Comment") or "").lower()
        or (isinstance(entry.get("Replace"), (bytes, bytearray)) and b"XCRS" in bytes(entry.get("Replace")))
        for entry in acpi_patches
    )
    if "SSDT-HPET.AML" in ssdt_paths and not xcrs:
        results.append({
            "level": "FAIL",
            "section": "ACPI -> Patch",
            "message": "SSDT-HPET.aml is enabled but HPET _CRS → XCRS is not. SSDTTime HPET does nothing until DSDT _CRS is renamed.",
            "remedy": "Enable ACPI patches HPET _CRS to XCRS Rename, TMR IRQ 0, and RTC IRQ 8 (Dell T5810 set)."
        })
    elif "SSDT-HPET.AML" in ssdt_paths and xcrs:
        results.append({
            "level": "PASS",
            "section": "ACPI -> Patch",
            "message": "HPET _CRS → XCRS is enabled with SSDT-HPET."
        })
    if "SSDT-X99-USBX.AML" in ssdt_paths:
        results.append({
            "level": "FAIL",
            "section": "ACPI -> Add",
            "message": "SSDT-X99-USBX.aml calls DTGP, which is not defined. That is the T5810 USBX table; it panics with AE_NOT_FOUND after replacing SSDT-SBUS-MCHC.",
            "remedy": "Disable SSDT-X99-USBX.aml. Keep SSDT-EC-USBX.aml — it injects the same USB power properties without DTGP."
        })
    for required, reason in (
        ("SSDT-RTC0-RANGE.AML", "Big Sur and newer RTC range on X99/C612"),
        ("SSDT-UNC.AML", "uncore PCI bridges on X99/C612"),
    ):
        if required not in ssdt_paths:
            results.append({
                "level": "FAIL",
                "section": "ACPI -> Add",
                "message": f"{required.replace('.AML', '.aml')} is missing. Dortania requires it for {reason}.",
                "remedy": f"Add and enable {required.replace('.AML', '.aml')} under ACPI -> Add, and copy the compiled AML into EFI/OC/ACPI."
            })

    drivers = [
        str(d.get("Path") or "").lower()
        for d in ((pl.get("UEFI") or {}).get("Drivers") or [])
        if d.get("Enabled", True)
    ]
    kext_paths = [
        str(e.get("BundlePath") or "").lower()
        for e in ((pl.get("Kernel") or {}).get("Add") or [])
        if e.get("Enabled", True)
    ]
    if any("resettcsadjust" in name for name in drivers):
        results.append({
            "level": "FAIL",
            "section": "UEFI -> Drivers",
            "message": "ResetTSCAdjust.efi is enabled, but OpenCore 1.0.x does not ship that file. A missing enabled driver halts boot.",
            "remedy": "Remove ResetTSCAdjust.efi from UEFI -> Drivers and add CpuTscSync.kext instead."
        })
    tsc_kext = any("cputscsync" in name or "tscadjustreset" in name for name in kext_paths)
    tsc_timeout = int(((pl.get("UEFI") or {}).get("Quirks") or {}).get("TscSyncTimeout") or 0)
    if not tsc_kext:
        results.append({
            "level": "FAIL",
            "section": "Kernel -> Add",
            "message": "CpuTscSync.kext is missing. Dell T5810/T7910 C612 firmware desyncs TSC and panics with Non-monotonic time on Monterey and newer.",
            "remedy": "Add CpuTscSync.kext under EFI/OC/Kexts (Lilu first) and enable it in Kernel -> Add. Do not list ResetTSCAdjust.efi; current OpenCore zips do not include that driver."
        })
    else:
        results.append({
            "level": "PASS",
            "section": "Kernel -> Add",
            "message": "CpuTscSync.kext is enabled for Dell T5810/T7910 TSC sync."
        })
    if tsc_timeout <= 0:
        results.append({
            "level": "WARN",
            "section": "UEFI -> Quirks",
            "message": "TscSyncTimeout is 0. A non-zero value helps cores sync before the kernel and CpuTscSync load.",
            "remedy": "Set UEFI -> Quirks -> TscSyncTimeout to 500000 (microseconds)."
        })
    if not any("resetnvram" in name for name in drivers):
        results.append({
            "level": "WARN",
            "section": "UEFI -> Drivers",
            "message": "ResetNvramEntry.efi is missing. In the OpenCore text picker press Spacebar if Reset NVRAM is hidden, then select it.",
            "remedy": "Enable ResetNvramEntry.efi under UEFI -> Drivers."
        })

    secure = str(((pl.get("Misc") or {}).get("Security") or {}).get("SecureBootModel") or "")
    if secure.lower() not in ("disabled",):
        results.append({
            "level": "FAIL",
            "section": "Misc -> Security",
            "message": f"SecureBootModel is {secure or 'empty'}, not Disabled. Sequoia installation on Dell X99 / T7910 needs Disabled.",
            "remedy": "Set Misc -> Security -> SecureBootModel to Disabled."
        })
    else:
        results.append({
            "level": "PASS",
            "section": "Misc -> Security",
            "message": "SecureBootModel is Disabled for the Sequoia X99 installer."
        })

    uefi_quirks = ((pl.get("UEFI") or {}).get("Quirks") or {})
    if uefi_quirks.get("ReleaseUsbOwnership"):
        results.append({
            "level": "FAIL",
            "section": "UEFI -> Quirks",
            "message": "ReleaseUsbOwnership is True. The known-working Dell X99 config keeps this False (weird USB / root-device behavior).",
            "remedy": "Set UEFI -> Quirks -> ReleaseUsbOwnership to False."
        })
    else:
        results.append({
            "level": "PASS",
            "section": "UEFI -> Quirks",
            "message": "ReleaseUsbOwnership is False (Dell X99 reference)."
        })
    if uefi_quirks.get("EnableVectorAcceleration"):
        results.append({
            "level": "FAIL",
            "section": "UEFI -> Quirks",
            "message": "EnableVectorAcceleration is True. The known-working Dell X99 config uses False.",
            "remedy": "Set UEFI -> Quirks -> EnableVectorAcceleration to False."
        })
    else:
        results.append({
            "level": "PASS",
            "section": "UEFI -> Quirks",
            "message": "EnableVectorAcceleration is False (Dell X99 reference)."
        })

    boot_args = str((((pl.get("NVRAM") or {}).get("Add") or {}).get("7C436110-AB2A-4BBB-A880-FE41995C9F82") or {}).get("boot-args") or "")
    if "cpus=1" in boot_args.split():
        results.append({
            "level": "WARN",
            "section": "NVRAM -> boot-args",
            "message": "boot-args still contains cpus=1, so macOS is restricted to one logical CPU. Fine as a diagnostic; remove it for a real install.",
            "remedy": "Remove cpus=1 from NVRAM boot-args after the single-core test."
        })

    return results
