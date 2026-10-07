"""OpenCore Studio — Master Plist Builder.

Assembles 100% compliant Apple XML config.plist files using official Sample.plist
as the canonical baseline template, applying hardware profiles, topologically sorted kexts,
dynamic AMD core patches, and SMBIOS information.
"""

from __future__ import annotations

import copy
import plistlib
import re
from typing import Any

from .acpi_patches import build_acpi_patch_entries, resolve_acpi_patch_ids
from .amd_patcher import get_amd_patches
from .drivers import default_driver_paths
from .kext_manager import build_kernel_add_entries
from .paths import mutable_file
from .profiles import get_profile
from .ssdts import OEM_SSDT_NAME, SKIP_ACPI_ADD, catalog_comment_for, profile_ssdt_paths

HEDT_PROFILE_IDS = {"intel_haswell_e", "intel_broadwell_e"}

SAMPLE_PLIST_PATH = mutable_file("Sample.plist")

# Dortania HEDT CPUID spoofs (Kernel -> Emulate). Haswell-E and Broadwell-E
# have no native XCPM support, so OpenCore must fake a supported CPUID.
HASWELL_E_CPUID = {
    "Cpuid1Data": "C3060300 00000000 00000000 00000000",
    "Cpuid1Mask": "FFFFFFFF 00000000 00000000 00000000",
}
BROADWELL_E_CPUID = {
    "Cpuid1Data": "D4060300 00000000 00000000 00000000",
    "Cpuid1Mask": "FFFFFFFF 00000000 00000000 00000000",
}


def _uefi_driver_entry(base_pl: dict[str, Any], path: str, comment: str = "", **extra: Any) -> dict[str, Any]:
    """Build a UEFI driver dict that matches the active Sample.plist schema."""
    entry: dict[str, Any] = {
        "Arguments": "",
        "Comment": comment,
        "Enabled": True,
        "LoadEarly": False,
        "Path": path,
    }
    sample = ((base_pl.get("UEFI") or {}).get("Drivers") or [])
    template = next((d for d in sample if isinstance(d, dict)), None)
    if template:
        for key, value in template.items():
            if key in extra:
                continue
            if key == "Path":
                entry[key] = path
            elif key == "Comment":
                entry[key] = comment
            elif key == "Enabled":
                entry[key] = True
            elif key == "LoadEarly":
                entry[key] = False
            elif key == "Arguments":
                entry[key] = ""
            elif isinstance(value, bool):
                entry[key] = False
            elif isinstance(value, str):
                entry[key] = ""
            else:
                entry[key] = value
    entry.update(extra)
    entry["Path"] = path
    if comment:
        entry["Comment"] = comment
    return entry


def _normalize_driver_path(item: Any) -> tuple[str, str, dict[str, Any]]:
    if isinstance(item, str):
        return item.strip(), "", {}
    if isinstance(item, dict):
        path = str(item.get("Path") or item.get("name") or item.get("path") or "").strip()
        comment = str(item.get("Comment") or item.get("reason") or item.get("description") or "")
        extra = {k: v for k, v in item.items() if k not in ("name", "reason", "path", "description", "id")}
        return path, comment, extra
    return "", "", {}


def _merge_uefi_drivers(
    base_pl: dict[str, Any],
    extras: list[Any] | None,
    selected: list[Any] | None = None,
) -> list[dict[str, Any]]:
    comments = {
        "OpenRuntime.efi": "OpenCore Runtime",
        "OpenHfsPlus.efi": "HFS+ Filesystem Driver",
        "ResetNvramEntry.efi": "Reset NVRAM Boot Option",
    }
    if isinstance(selected, list) and selected:
        raw = list(selected)
        if not any(_normalize_driver_path(item)[0].lower() == "openruntime.efi" for item in raw):
            raw.insert(0, "OpenRuntime.efi")
    else:
        raw = [
            "OpenRuntime.efi",
            "OpenHfsPlus.efi",
            "ResetNvramEntry.efi",
            *(extras or []),
        ]
    drivers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        path, comment, extra = _normalize_driver_path(item)
        if not path or path.lower() in seen:
            continue
        if path.lower() == "resettcsadjust.efi":
            continue
        seen.add(path.lower())
        extra_args = {k: v for k, v in extra.items() if k not in ("Path", "Comment", "path")}
        drivers.append(_uefi_driver_entry(
            base_pl,
            path,
            comment or comments.get(path, ""),
            **extra_args,
        ))
    return drivers


def _apply_hedt_next_test(base_pl: dict[str, Any], profile_id: str) -> None:
    """Dell X99 / T7910 Sequoia installer set. Stale sessions still carry Sample defaults."""
    if profile_id not in HEDT_PROFILE_IDS:
        return
    base_pl.setdefault("Misc", {}).setdefault("Security", {})
    base_pl["Misc"]["Security"]["SecureBootModel"] = "Disabled"
    uq = base_pl.setdefault("UEFI", {}).setdefault("Quirks", {})
    if "ReleaseUsbOwnership" in uq:
        uq["ReleaseUsbOwnership"] = False
    if "EnableVectorAcceleration" in uq:
        uq["EnableVectorAcceleration"] = False


def load_base_sample() -> dict[str, Any]:
    if not SAMPLE_PLIST_PATH.exists():
        raise FileNotFoundError(f"Canonical Sample.plist not found at {SAMPLE_PLIST_PATH}")
    with open(SAMPLE_PLIST_PATH, "rb") as f:
        return plistlib.load(f)


def _plist_bytes(value: Any) -> bytes:
    """Turn profile hex / lists into OpenCore DATA values."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, list):
        return bytes(int(x) & 0xFF for x in value)
    text = str(value or "").strip()
    if not text:
        return b""
    text = re.sub(r"(?i)0x", "", text)
    text = re.sub(r"[^0-9A-Fa-f]", "", text)
    if len(text) % 2:
        text = "0" + text
    try:
        return bytes.fromhex(text)
    except ValueError:
        return b""


def kext_ids_for_build(options: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    """UI selection plus any kexts the profile cannot boot without."""
    selected = options.get("selectedKextIds")
    if not isinstance(selected, list) or not selected:
        selected = list(profile.get("recommendedKexts") or ["Lilu", "VirtualSMC"])
    else:
        selected = [str(k) for k in selected if k]
    seen = {k.lower() for k in selected}
    for kid in profile.get("mandatoryKexts") or []:
        name = str(kid or "").strip()
        if name and name.lower() not in seen:
            selected.append(name)
            seen.add(name.lower())
    return selected


def _apply_quirks(target: dict[str, Any], updates: dict[str, Any] | None) -> None:
    if not updates or not isinstance(target, dict):
        return
    for key, value in updates.items():
        if key in target:
            target[key] = value


def _cpu_query_blob(options: dict[str, Any], profile: dict[str, Any]) -> str:
    hw = options.get("hardwareInfo") or {}
    parts = [
        str(options.get("cpuQuery") or ""),
        str(hw.get("cpuQuery") or ""),
        str(hw.get("cpuFamily") or ""),
        str(profile.get("id") or ""),
        str(profile.get("cpuFamily") or ""),
        str(profile.get("name") or ""),
    ]
    return " ".join(parts).upper()


def _cpuid_spoof_for_options(options: dict[str, Any], profile: dict[str, Any]) -> dict[str, str] | None:
    """Pick Haswell-E vs Broadwell-E CPUID from the typed SKU when present."""
    blob = _cpu_query_blob(options, profile)
    compact = re.sub(r"[\s\-]", "", blob)
    profile_id = str(profile.get("id") or "")
    if re.search(r"V4|I[3579]6[89]\d{2}|BROADWELL", compact):
        return dict(BROADWELL_E_CPUID)
    if re.search(r"V3|I[3579]5[89]\d{2}|HASWELL-E|HASWELLE|INTEL_HASWELL_E", compact):
        return dict(HASWELL_E_CPUID)
    if profile_id == "intel_broadwell_e":
        return dict(BROADWELL_E_CPUID)
    if profile_id == "intel_haswell_e":
        return dict(HASWELL_E_CPUID)
    return None


def _apply_kernel_emulate(emulate_section: dict[str, Any], updates: dict[str, Any] | None) -> None:
    if not updates:
        return
    for key, value in updates.items():
        if key in ("Cpuid1Data", "Cpuid1Mask"):
            emulate_section[key] = _plist_bytes(value)
        else:
            emulate_section[key] = value


def build_config_plist(options: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Builds an OpenCore config.plist dictionary and its serialized XML string."""
    base_pl = copy.deepcopy(load_base_sample())
    profile_id = options.get("profileId", "intel_comet_lake")
    profile = get_profile(profile_id) or {}

    # 1. ACPI Section
    base_pl.setdefault("ACPI", {})
    acpi_add = []
    selected_ssdts = options.get("selectedSsdts")
    if isinstance(selected_ssdts, list):
        raw_ssdts = [str(s).strip() for s in selected_ssdts if str(s).strip()]
    else:
        raw_ssdts = profile_ssdt_paths(profile)
    reasons = {}
    for item in profile.get("mandatorySsdt") or []:
        if isinstance(item, dict) and item.get("name"):
            reasons[str(item["name"]).lower()] = item.get("reason") or ""
    seen_ssdt: set[str] = set()
    selected_keys = {str(s).strip().lower() for s in raw_ssdts}
    drop_x99_usbx = "ssdt-ec-usbx.aml" in selected_keys
    for ssdt_name in raw_ssdts:
        key = ssdt_name.lower()
        if not ssdt_name or key in seen_ssdt:
            continue
        if key in SKIP_ACPI_ADD or OEM_SSDT_NAME.match(key):
            continue
        if drop_x99_usbx and key == "ssdt-x99-usbx.aml":
            continue
        seen_ssdt.add(key)
        comment = reasons.get(key) or catalog_comment_for(ssdt_name)
        acpi_add.append({
            "Arguments": "",
            "Comment": comment,
            "Enabled": True,
            "Path": ssdt_name,
        })
    base_pl["ACPI"]["Add"] = acpi_add
    patch_ids = resolve_acpi_patch_ids(options, profile, raw_ssdts)
    base_pl["ACPI"]["Patch"] = build_acpi_patch_entries(base_pl, patch_ids)

    acpi_quirks = profile.get("acpiQuirks", {}) or profile.get("acpi", {}).get("quirks", {})
    base_pl["ACPI"].setdefault("Quirks", {})
    _apply_quirks(base_pl["ACPI"]["Quirks"], acpi_quirks)

    # 2. Booter Section
    base_pl.setdefault("Booter", {}).setdefault("Quirks", {})
    booter_quirks = profile.get("booterQuirks", {}) or profile.get("booter", {}).get("quirks", {})
    _apply_quirks(base_pl["Booter"]["Quirks"], booter_quirks)

    # 3. DeviceProperties — Sample.plist ships a dummy audio PciRoot; Dortania
    # says to delete it unless the profile actually sets framebuffer/audio props.
    base_pl.setdefault("DeviceProperties", {})
    dev_props = profile.get("deviceProperties", {})
    if isinstance(dev_props, dict) and "Add" in dev_props:
        add_props = copy.deepcopy(dev_props.get("Add") or {})
    elif isinstance(dev_props, dict) and dev_props:
        add_props = copy.deepcopy(dev_props)
    else:
        add_props = {}
    base_pl["DeviceProperties"]["Add"] = add_props

    # 4. Kernel Section
    base_pl.setdefault("Kernel", {})

    selected_kexts = kext_ids_for_build(options, profile)
    sorted_kext_entries = build_kernel_add_entries(selected_kexts)
    base_pl["Kernel"]["Add"] = sorted_kext_entries

    base_pl["Kernel"].setdefault("Quirks", {})
    kernel_quirks = profile.get("kernelQuirks", {}) or profile.get("kernel", {}).get("quirks", {})
    _apply_quirks(base_pl["Kernel"]["Quirks"], kernel_quirks)

    base_pl["Kernel"].setdefault("Emulate", {})
    kernel_emulate = dict(profile.get("kernelEmulate", {}) or profile.get("kernel", {}).get("emulate", {}) or {})
    spoof = _cpuid_spoof_for_options(options, profile)
    if spoof:
        kernel_emulate.update(spoof)
        kernel_emulate.setdefault("DummyPowerManagement", False)
    user_emulate = options.get("kernelEmulate")
    if isinstance(user_emulate, dict):
        kernel_emulate.update(user_emulate)
    _apply_kernel_emulate(base_pl["Kernel"]["Emulate"], kernel_emulate)

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
    base_pl["Misc"]["Boot"]["HideAuxiliary"] = True
    misc_boot = profile.get("miscBoot") or {}
    for key, value in misc_boot.items():
        if key in base_pl["Misc"]["Boot"]:
            base_pl["Misc"]["Boot"][key] = value

    base_pl["Misc"].setdefault("Debug", {})
    base_pl["Misc"]["Debug"]["AppleDebug"] = True
    base_pl["Misc"]["Debug"]["ApplePanic"] = True
    base_pl["Misc"]["Debug"]["DisableWatchDog"] = True
    base_pl["Misc"]["Debug"]["Target"] = 67

    base_pl["Misc"].setdefault("Security", {})
    base_pl["Misc"]["Security"]["AllowSetDefault"] = True
    base_pl["Misc"]["Security"]["BlacklistAppleUpdate"] = True
    base_pl["Misc"]["Security"]["ScanPolicy"] = 0
    base_pl["Misc"]["Security"]["SecureBootModel"] = "Default"
    base_pl["Misc"]["Security"]["Vault"] = "Optional"
    misc_security = profile.get("miscSecurity") or {}
    for key, value in misc_security.items():
        if key in base_pl["Misc"]["Security"]:
            base_pl["Misc"]["Security"][key] = value
    if options.get("secureBootModel"):
        base_pl["Misc"]["Security"]["SecureBootModel"] = str(options["secureBootModel"])

    # 6. NVRAM Section
    base_pl.setdefault("NVRAM", {}).setdefault("Add", {})
    apple_guid = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
    base_pl["NVRAM"]["Add"].setdefault(apple_guid, {})

    boot_args = options.get("bootArgs")
    if not boot_args:
        boot_args = profile.get("recommendedBootArgs") or profile.get("bootArgs")
        if isinstance(boot_args, list):
            boot_args = " ".join(str(a) for a in boot_args)
        if not boot_args:
            boot_args = "-v keepsyms=1 debug=0x100"
    base_pl["NVRAM"]["Add"][apple_guid]["boot-args"] = boot_args
    base_pl["NVRAM"]["Add"][apple_guid]["prev-lang:kbd"] = "en-US:0"
    base_pl["NVRAM"]["Add"][apple_guid]["run-efi-updater"] = "No"

    nvram_cfg = profile.get("nvram") or {}
    if "LegacyOverwrite" in nvram_cfg:
        base_pl["NVRAM"]["LegacyOverwrite"] = bool(nvram_cfg["LegacyOverwrite"])
    if "WriteFlash" in nvram_cfg:
        base_pl["NVRAM"]["WriteFlash"] = bool(nvram_cfg["WriteFlash"])

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
    extra_drivers = profile.get("uefiDrivers") or profile.get("uefi", {}).get("drivers") or []
    selected_drivers = options.get("selectedDrivers")
    if not selected_drivers:
        selected_drivers = default_driver_paths(profile)
    base_pl["UEFI"]["Drivers"] = _merge_uefi_drivers(base_pl, extra_drivers, selected_drivers)
    base_pl["UEFI"].setdefault("Quirks", {})
    base_pl["UEFI"]["Quirks"]["RequestBootVarRouting"] = True
    base_pl["UEFI"]["Quirks"]["UnblockFsConnect"] = False
    uefi_quirks = profile.get("uefiQuirks", {}) or profile.get("uefi", {}).get("quirks", {})
    _apply_quirks(base_pl["UEFI"]["Quirks"], uefi_quirks)
    base_pl["UEFI"].setdefault("Output", {})
    if "ProvideConsoleGop" in base_pl["UEFI"]["Output"]:
        base_pl["UEFI"]["Output"]["ProvideConsoleGop"] = True

    quirk_overrides = options.get("quirkOverrides", {})
    for sec, quirks in quirk_overrides.items():
        if sec in base_pl and isinstance(base_pl[sec], dict) and "Quirks" in base_pl[sec]:
            _apply_quirks(base_pl[sec]["Quirks"], quirks if isinstance(quirks, dict) else {})

    _apply_hedt_next_test(base_pl, profile_id)

    # Sample.plist ships Acidanthera "do not boot this" warnings. This file is a
    # real Studio build, so drop those keys and label it as generated.
    for key in [k for k in list(base_pl.keys()) if str(k).startswith("#")]:
        del base_pl[key]
    base_pl["#OpenCore Studio"] = (
        f"Generated config.plist for profile '{profile_id}'. "
        "This is not Acidanthera Sample.plist — it is intended for the EFI folder you built."
    )

    xml_bytes = plistlib.dumps(base_pl, fmt=plistlib.FMT_XML, sort_keys=True)
    xml_str = xml_bytes.decode("utf-8")

    return base_pl, xml_str
