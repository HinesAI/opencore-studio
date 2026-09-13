"""OpenCore Studio — Master Plist Builder.

Assembles 100% compliant Apple XML config.plist files using official Sample.plist
as the canonical baseline template, applying hardware profiles, topologically sorted kexts,
dynamic AMD core patches, and SMBIOS information.
"""

from __future__ import annotations

import copy
import plistlib
from pathlib import Path
from typing import Any

from .amd_patcher import get_amd_patches
from .kext_manager import build_kernel_add_entries
from .paths import mutable_file
from .profiles import get_profile

SAMPLE_PLIST_PATH = mutable_file("Sample.plist")


def load_base_sample() -> dict[str, Any]:
    if not SAMPLE_PLIST_PATH.exists():
        raise FileNotFoundError(f"Canonical Sample.plist not found at {SAMPLE_PLIST_PATH}")
    with open(SAMPLE_PLIST_PATH, "rb") as f:
        return plistlib.load(f)


def build_config_plist(options: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Builds an OpenCore config.plist dictionary and its serialized XML string."""
    base_pl = copy.deepcopy(load_base_sample())
    profile_id = options.get("profileId", "intel_comet_lake")
    profile = get_profile(profile_id) or {}

    # 1. ACPI Section
    base_pl.setdefault("ACPI", {})
    acpi_add = []
    # Build SSDT entries from profile
    raw_ssdts = profile.get("mandatorySsdt", []) or profile.get("acpi", {}).get("ssdts", [])
    for ssdt_item in raw_ssdts:
        if isinstance(ssdt_item, dict):
            ssdt_name = ssdt_item.get("name", "")
            comment = ssdt_item.get("reason", f"SSDT {ssdt_name}")
        else:
            ssdt_name = str(ssdt_item)
            comment = f"OpenCore Studio Generated: {ssdt_name}"

        if ssdt_name:
            acpi_add.append({
                "Arguments": "",
                "Comment": comment,
                "Enabled": True,
                "Path": ssdt_name,
            })
    base_pl["ACPI"]["Add"] = acpi_add

    # Apply ACPI Quirks
    acpi_quirks = profile.get("acpiQuirks", {}) or profile.get("acpi", {}).get("quirks", {})
    base_pl["ACPI"].setdefault("Quirks", {})
    for qk, qv in acpi_quirks.items():
        if qk in base_pl["ACPI"]["Quirks"]:
            base_pl["ACPI"]["Quirks"][qk] = qv

    # 2. Booter Section
    base_pl.setdefault("Booter", {}).setdefault("Quirks", {})
    booter_quirks = profile.get("booterQuirks", {}) or profile.get("booter", {}).get("quirks", {})
    for qk, qv in booter_quirks.items():
        if qk in base_pl["Booter"]["Quirks"]:
            base_pl["Booter"]["Quirks"][qk] = qv

    # 3. DeviceProperties
    base_pl.setdefault("DeviceProperties", {}).setdefault("Add", {})
    dev_props = profile.get("deviceProperties", {}).get("Add", {}) or profile.get("deviceProperties", {})
    # If deviceProperties has nested structure or raw dictionary
    if dev_props:
        base_pl["DeviceProperties"]["Add"] = copy.deepcopy(dev_props)

    # 4. Kernel Section
    base_pl.setdefault("Kernel", {})

    # Topologically sort and format kexts
    selected_kexts = options.get("selectedKextIds")
    if not selected_kexts:
        selected_kexts = profile.get("recommendedKexts", ["Lilu", "VirtualSMC"])
    sorted_kext_entries = build_kernel_add_entries(selected_kexts)
    base_pl["Kernel"]["Add"] = sorted_kext_entries

    # Kernel Quirks
    base_pl["Kernel"].setdefault("Quirks", {})
    kernel_quirks = profile.get("kernelQuirks", {}) or profile.get("kernel", {}).get("quirks", {})
    for qk, qv in kernel_quirks.items():
        if qk in base_pl["Kernel"]["Quirks"]:
            base_pl["Kernel"]["Quirks"][qk] = qv

    # Kernel Emulate (for AMD or VMs)
    base_pl["Kernel"].setdefault("Emulate", {})
    kernel_emulate = profile.get("kernelEmulate", {}) or profile.get("kernel", {}).get("emulate", {})
    for ek, ev in kernel_emulate.items():
        base_pl["Kernel"]["Emulate"][ek] = ev

    # Kernel Patches (e.g. AMD Vanilla Patches)
    profile_arch = profile.get("architecture", "")
    if profile_arch == "AMD" or "amd" in profile_id.lower() or "ryzen" in profile_id.lower():
        core_count = options.get("amdCoreCount", 8)
        base_pl["Kernel"]["Patch"] = get_amd_patches(core_count)
    else:
        base_pl["Kernel"]["Patch"] = []

    # 5. Misc Section (Production Hackintosh defaults)
    base_pl.setdefault("Misc", {})
    base_pl["Misc"].setdefault("Boot", {})
    base_pl["Misc"]["Boot"]["ShowPicker"] = True
    base_pl["Misc"]["Boot"]["PickerMode"] = "External"
    base_pl["Misc"]["Boot"]["PickerVariant"] = "Acidanthera\\GoldenGate"
    base_pl["Misc"]["Boot"]["Timeout"] = 5
    base_pl["Misc"]["Boot"]["HibernateMode"] = "None"

    base_pl["Misc"].setdefault("Debug", {})
    base_pl["Misc"]["Debug"]["AppleDebug"] = True
    base_pl["Misc"]["Debug"]["ApplePanic"] = True
    base_pl["Misc"]["Debug"]["DisableWatchDog"] = True
    base_pl["Misc"]["Debug"]["Target"] = 67

    base_pl["Misc"].setdefault("Security", {})
    base_pl["Misc"]["Security"]["AllowSetDefault"] = True
    base_pl["Misc"]["Security"]["ScanPolicy"] = 0
    base_pl["Misc"]["Security"]["SecureBootModel"] = "Default"
    base_pl["Misc"]["Security"]["Vault"] = "Optional"

    # 6. NVRAM Section
    base_pl.setdefault("NVRAM", {}).setdefault("Add", {})
    apple_guid = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
    base_pl["NVRAM"]["Add"].setdefault(apple_guid, {})

    # Boot args
    boot_args = options.get("bootArgs")
    if not boot_args:
        boot_args = profile.get("recommendedBootArgs", "-v keepsyms=1 debug=0x100")
    base_pl["NVRAM"]["Add"][apple_guid]["boot-args"] = boot_args
    base_pl["NVRAM"]["Add"][apple_guid]["prev-lang:kbd"] = "en-US:0"

    # 7. PlatformInfo (SMBIOS)
    base_pl.setdefault("PlatformInfo", {})
    base_pl["PlatformInfo"]["Automatic"] = True
    base_pl["PlatformInfo"]["CustomMemory"] = False
    base_pl["PlatformInfo"]["UpdateDataHub"] = True
    base_pl["PlatformInfo"]["UpdateNVRAM"] = True
    base_pl["PlatformInfo"]["UpdateSMBIOS"] = True
    base_pl["PlatformInfo"]["UpdateSMBIOSMode"] = "Create"
    base_pl["PlatformInfo"].setdefault("Generic", {})

    smbios_data = options.get("smbios", {})
    rec_smbios = profile.get("recommendedSmbios", "iMac20,1")
    if isinstance(rec_smbios, dict):
        rec_model = rec_smbios.get("igpu_only") or rec_smbios.get("default") or list(rec_smbios.values())[0]
    else:
        rec_model = str(rec_smbios)

    model = smbios_data.get("model") or rec_model
    base_pl["PlatformInfo"]["Generic"]["SystemProductName"] = model
    base_pl["PlatformInfo"]["Generic"]["SystemSerialNumber"] = smbios_data.get("serial", "")
    base_pl["PlatformInfo"]["Generic"]["MLB"] = smbios_data.get("mlb", "")
    base_pl["PlatformInfo"]["Generic"]["SystemUUID"] = smbios_data.get("uuid", "")
    raw_rom = smbios_data.get("rom", "112233445566").replace(":", "").replace("-", "")
    try:
        base_pl["PlatformInfo"]["Generic"]["ROM"] = bytes.fromhex(raw_rom)
    except ValueError:
        base_pl["PlatformInfo"]["Generic"]["ROM"] = b"\x11\x22\x33\x44\x55\x66"

    # 8. UEFI Drivers
    base_pl.setdefault("UEFI", {}).setdefault("Drivers", [])
    base_pl["UEFI"]["Drivers"] = [
        {"Arguments": "", "Comment": "OpenCore Runtime", "Enabled": True, "LoadEarly": False, "Path": "OpenRuntime.efi"},
        {"Arguments": "", "Comment": "HFS+ Filesystem Driver", "Enabled": True, "LoadEarly": False, "Path": "OpenHfsPlus.efi"},
        {"Arguments": "", "Comment": "Reset NVRAM Boot Option", "Enabled": True, "LoadEarly": False, "Path": "ResetNvramEntry.efi"},
    ]
    base_pl["UEFI"].setdefault("Quirks", {})
    base_pl["UEFI"]["Quirks"]["RequestBootVarRouting"] = True
    base_pl["UEFI"]["Quirks"]["UnblockFsConnect"] = False

    # Apply manual quirk overrides if any
    quirk_overrides = options.get("quirkOverrides", {})
    for sec, quirks in quirk_overrides.items():
        if sec in base_pl and isinstance(base_pl[sec], dict) and "Quirks" in base_pl[sec]:
            for qk, qv in quirks.items():
                base_pl[sec]["Quirks"][qk] = qv

    # Sample.plist ships Acidanthera "do not boot this" warnings. This file is a
    # real Studio build, so drop those keys and label it as generated.
    for key in [k for k in list(base_pl.keys()) if str(k).startswith("#")]:
        del base_pl[key]
    base_pl["#OpenCore Studio"] = (
        f"Generated config.plist for profile '{profile_id}'. "
        "This is not Acidanthera Sample.plist — it is intended for the EFI folder you built."
    )

    # Serialize to XML plist
    xml_bytes = plistlib.dumps(base_pl, fmt=plistlib.FMT_XML, sort_keys=True)
    xml_str = xml_bytes.decode("utf-8")

    return base_pl, xml_str
