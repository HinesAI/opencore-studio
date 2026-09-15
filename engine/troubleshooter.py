"""Dortania-based boot troubleshooter.

Maps verbose-log snippets and the current kext/quirk setup onto the same
fixes Dortania documents for USB maps, 15-port limit, and early kernel stalls.
Does not scrape the live site; advice is paraphrased with guide links.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .efi_builder import last_manifest

DORTANIA_KERNEL = "https://dortania.github.io/OpenCore-Install-Guide/troubleshooting/extended/kernel-issues.html"
DORTANIA_USB = "https://dortania.github.io/OpenCore-Post-Install/usb/"
DORTANIA_INTEL_MAP = "https://dortania.github.io/OpenCore-Post-Install/usb/intel-mapping/intel.html"

SYMPTOMS: list[dict[str, Any]] = [
    {
        "id": "usb_map_kext",
        "title": "USB kext / USB map not loaded",
        "blurb": "Boot halts mentioning USBToolBox, UTBMap, USBMap, USB layout, or a USB kext that did not load. Keyboard and mouse often die in the installer.",
        "keywords": [
            "usbtoolbox",
            "utbmap",
            "usbmap",
            "usb kext",
            "usb layout",
            "map kext",
            "kext wasn't loaded",
            "kext was not loaded",
            "failed to load kext",
        ],
        "guide": DORTANIA_USB,
        "also": DORTANIA_INTEL_MAP,
        "advice": (
            "A USB port map is unique to the board. Studio can enable USBToolBox, but it cannot "
            "ship your UTBMap.kext — that file is generated on the target PC. For the installer USB, "
            "leave USBToolBox and UTBMap off, keep XhciPortLimit disabled on macOS 11.3+, and enable "
            "XHCI Hand-off in firmware. After macOS is installed, map ports with USBToolBox or CorpNewt "
            "USBMap and only then add the map kext."
        ),
        "fixes": {
            "removeKexts": ["USBToolBox", "UTBMap", "USBInjectAll"],
            "setQuirks": {
                "Kernel": {"XhciPortLimit": False},
                "UEFI": {"ReleaseUsbOwnership": True},
            },
        },
    },
    {
        "id": "waiting_root_device",
        "title": "Waiting for Root Device / prohibited sign",
        "blurb": "Installer USB never appears as a disk. Stop sign, scrambled icon, or 'Waiting for Root Device'.",
        "keywords": [
            "waiting for root device",
            "prohibited",
            "stop sign",
            "still waiting for root",
        ],
        "guide": DORTANIA_KERNEL,
        "advice": (
            "Dortania treats this as USB ownership or the 15-port limit on the installer stick. "
            "Try a USB 2.0 port (or the other way around), enable XHCI/EHCI Hand-off, set "
            "UEFI → Quirks → ReleaseUsbOwnership, and do not use a generic USB map. Ice Lake / "
            "Comet Lake often need SSDT-RHUB; AMD uses SSDTTime USB Reset."
        ),
        "fixes": {
            "removeKexts": ["USBToolBox", "UTBMap"],
            "setQuirks": {
                "Kernel": {"XhciPortLimit": False},
                "UEFI": {"ReleaseUsbOwnership": True},
            },
        },
    },
    {
        "id": "appleusbhostport",
        "title": "AppleUSBHostPort failed to create device (11.3+)",
        "blurb": "Reboot loop on 'AppleUSBHostPort::createDevice: failed to create device' from Big Sur 11.3 onward.",
        "keywords": [
            "appleusbhostport",
            "failed to create device",
            "xhciportlimit",
        ],
        "guide": DORTANIA_KERNEL,
        "advice": (
            "XhciPortLimit is broken on macOS 11.3+. Disable Kernel → Quirks → XhciPortLimit. "
            "Do not rely on that quirk instead of a real USB map."
        ),
        "fixes": {
            "setQuirks": {"Kernel": {"XhciPortLimit": False}},
        },
    },
    {
        "id": "plist_only_executable",
        "title": "Plist-only kext has CFBundleExecutable",
        "blurb": "OpenCore stops because a map kext has an ExecutablePath even though it has no binary.",
        "keywords": [
            "plist only kext",
            "cfbundleexecutable",
            "invalid parameter",
        ],
        "guide": DORTANIA_KERNEL,
        "advice": (
            "USBMap.kext and UTBMap.kext are Info.plist only. Kernel → Add → ExecutablePath must be empty. "
            "Studio already leaves UTBMap’s executable path blank; if you imported a plist, clear it."
        ),
        "fixes": {},
    },
    {
        "id": "exitbs",
        "title": "Stuck on EXITBS:START / EndRandomSeed",
        "blurb": "Stops at [EB|#LOG:EXITBS:START] or EndRandomSeed before the Apple logo progress bar.",
        "keywords": [
            "exitbs",
            "endrandomseed",
            "log:exitbs",
        ],
        "guide": DORTANIA_KERNEL,
        "advice": (
            "This is almost always Booter quirks or AMD kernel patches, not USB. Check SetupVirtualMap "
            "for your chipset year, EnableWriteUnprotector vs MAT-style RebuildAppleMemoryMap, and "
            "(on Ryzen) that AMD Vanilla patches are present and current."
        ),
        "fixes": {},
    },
    {
        "id": "navi_black",
        "title": "Black screen after gIOScreenLock (Navi)",
        "blurb": "Gets past verbose text, then the display goes black on RX 5000/6000.",
        "keywords": [
            "gioscreenlock",
            "giolockstate",
            "agdpmod",
        ],
        "guide": DORTANIA_KERNEL,
        "advice": "Add agdpmod=pikera to boot-args for Navi, try another display output, and confirm the GPU is UEFI-capable.",
        "fixes": {"addBootArgs": ["agdpmod=pikera"]},
    },
    {
        "id": "kextd_stall_smc",
        "title": "kextd stall AppleACPICPU / missing SMC",
        "blurb": "Stall or panic because Lilu/VirtualSMC are missing, out of order, or both VirtualSMC and FakeSMC are on.",
        "keywords": [
            "kextd stall",
            "appleacpicpu",
            "cckprng",
        ],
        "guide": DORTANIA_KERNEL,
        "advice": "Lilu.kext first, then VirtualSMC. Never enable FakeSMC alongside it.",
        "fixes": {},
    },
    {
        "id": "secure_boot",
        "title": "LoadImage failed — Security Violation",
        "blurb": "OCB: LoadImage failed - Security Violation with SecureBootModel enabled.",
        "keywords": [
            "security violation",
            "no suitable signature",
            "apple secure boot",
        ],
        "guide": DORTANIA_KERNEL,
        "advice": "Set Misc → Security → SecureBootModel to Disabled for the installer, or restore Apple Secure Boot manifests on Preboot.",
        "fixes": {},
    },
    {
        "id": "smbios_unsupported",
        "title": "This version of Mac OS X is not supported",
        "blurb": "SMBIOS model is too old for the macOS version on the stick.",
        "keywords": [
            "this version of mac os x is not supported",
            "reason mac",
        ],
        "guide": DORTANIA_KERNEL,
        "advice": "Pick an SMBIOS Dortania lists for that OS (Ventura needs iMac18,x+ / MacPro7,1, etc.) and keep PlatformInfo → Generic → Automatic enabled.",
        "fixes": {},
    },
]


def list_symptoms() -> dict[str, Any]:
    rows = []
    for item in SYMPTOMS:
        rows.append({
            "id": item["id"],
            "title": item["title"],
            "blurb": item["blurb"],
            "guide": item["guide"],
            "also": item.get("also") or "",
        })
    return {
        "success": True,
        "guide": DORTANIA_KERNEL,
        "usbGuide": DORTANIA_USB,
        "symptoms": rows,
    }


def _ids_from_payload(body: dict[str, Any]) -> list[str]:
    ids = [str(x) for x in (body.get("selectedKextIds") or []) if x]
    if ids:
        return ids
    pl = body.get("config") or {}
    found = []
    for entry in pl.get("Kernel", {}).get("Add", []) or []:
        if not entry.get("Enabled", True):
            continue
        bundle = str(entry.get("BundlePath") or "")
        stem = Path(bundle).name.replace(".kext", "")
        if stem:
            found.append(stem)
    return found


def _quirks_from_payload(body: dict[str, Any]) -> dict[str, Any]:
    overrides = body.get("quirkOverrides") or {}
    pl = body.get("config") or {}
    kernel = dict(pl.get("Kernel", {}).get("Quirks") or {})
    uefi = dict(pl.get("UEFI", {}).get("Quirks") or {})
    kernel.update((overrides.get("Kernel") or {}))
    uefi.update((overrides.get("UEFI") or {}))
    return {"Kernel": kernel, "UEFI": uefi}


def _cpu_blob(body: dict[str, Any]) -> str:
    hw = body.get("hardwareInfo") or {}
    return " ".join(
        str(hw.get(key) or "")
        for key in ("cpuFamily", "architecture", "profileId", "gpuType")
    ).lower()


def _efi_has_kext(name: str) -> bool:
    manifest = last_manifest()
    efi = Path(manifest.get("efiPath") or "")
    if not efi.exists():
        return False
    return (efi / "OC" / "Kexts" / name).is_dir()


def usb_setup_findings(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Config checks for USB maps — the usual installer halt."""
    ids = set(_ids_from_payload(body))
    quirks = _quirks_from_payload(body)
    cpu = _cpu_blob(body)
    results: list[dict[str, Any]] = []
    has_toolbox = "USBToolBox" in ids
    has_utbmap = "UTBMap" in ids
    has_usbmap = "USBMap" in ids
    has_injectall = any(x.lower() == "usbinjectall" or "usbinjectall" in x.lower() for x in ids)
    utbmap_on_disk = _efi_has_kext("UTBMap.kext")
    usbmap_on_disk = _efi_has_kext("USBMap.kext")
    xhci = bool(quirks.get("Kernel", {}).get("XhciPortLimit"))
    release = quirks.get("UEFI", {}).get("ReleaseUsbOwnership")

    if has_toolbox and not (utbmap_on_disk or usbmap_on_disk):
        results.append({
            "level": "FAIL",
            "section": "USB map",
            "symptomId": "usb_map_kext",
            "message": "USBToolBox.kext is enabled, but no UTBMap.kext/USBMap.kext is in the built EFI. USBToolBox will log that the map kext was not loaded and USB layout can halt the installer.",
            "remedy": "Uncheck USBToolBox and UTBMap for the first installer USB. Map ports after install, then add your generated UTBMap.kext.",
            "guide": DORTANIA_USB,
            "fixes": SYMPTOMS[0]["fixes"],
        })
    elif has_utbmap and not utbmap_on_disk:
        results.append({
            "level": "FAIL",
            "section": "USB map",
            "symptomId": "usb_map_kext",
            "message": "UTBMap is selected, but Studio never downloads it — a USB map has to be generated on the target machine.",
            "remedy": "Remove UTBMap from the kext list until you have a real map. OpenCore will otherwise list a kext that is not in EFI/OC/Kexts.",
            "guide": DORTANIA_INTEL_MAP,
            "fixes": SYMPTOMS[0]["fixes"],
        })
    elif has_usbmap and not usbmap_on_disk:
        results.append({
            "level": "WARN",
            "section": "USB map",
            "symptomId": "usb_map_kext",
            "message": "USBMap.kext is selected but not present in the last EFI build.",
            "remedy": "Copy your generated USBMap.kext into the EFI or deselect it until you have one.",
            "guide": DORTANIA_INTEL_MAP,
        })
    elif has_toolbox and (utbmap_on_disk or usbmap_on_disk):
        results.append({
            "level": "PASS",
            "section": "USB map",
            "message": "USBToolBox is enabled and a USB map kext is present in the built EFI.",
        })

    if has_injectall and ("amd" in cpu or "ryzen" in cpu or "epyc" in cpu):
        results.append({
            "level": "FAIL",
            "section": "USBInjectAll",
            "symptomId": "usb_map_kext",
            "message": "USBInjectAll does not work on AMD. Dortania uses SSDT-RHUB / USBToolBox mapping instead.",
            "remedy": "Disable USBInjectAll. Map USB after install.",
            "guide": DORTANIA_USB,
            "fixes": {"removeKexts": ["USBInjectAll"]},
        })

    if has_injectall and (has_toolbox or has_utbmap or has_usbmap):
        results.append({
            "level": "FAIL",
            "section": "USB map",
            "symptomId": "usb_map_kext",
            "message": "USBInjectAll plus a USB map kext will fight. Dortania: drop USBInjectAll once a map exists.",
            "remedy": "Keep only the map kext (and USBToolBox if the map is UTBMap).",
            "guide": DORTANIA_USB,
            "fixes": {"removeKexts": ["USBInjectAll"]},
        })

    if xhci:
        results.append({
            "level": "FAIL",
            "section": "Kernel → Quirks",
            "symptomId": "appleusbhostport",
            "message": "XhciPortLimit is enabled. On macOS 11.3+ this reboots on AppleUSBHostPort::createDevice.",
            "remedy": "Set XhciPortLimit to False. Use a real USB map after install instead of the 15-port quirk.",
            "guide": DORTANIA_KERNEL,
            "fixes": {"setQuirks": {"Kernel": {"XhciPortLimit": False}}},
        })

    if release is False:
        results.append({
            "level": "WARN",
            "section": "UEFI → Quirks",
            "symptomId": "waiting_root_device",
            "message": "ReleaseUsbOwnership is False. Some firmware will not hand USB to the installer (Waiting for Root Device).",
            "remedy": "Enable UEFI → Quirks → ReleaseUsbOwnership and XHCI Hand-off in BIOS.",
            "guide": DORTANIA_KERNEL,
            "fixes": {"setQuirks": {"UEFI": {"ReleaseUsbOwnership": True}}},
        })

    return results


def _match_symptoms(log: str, picked: list[str]) -> list[dict[str, Any]]:
    hay = " ".join(str(log or "").lower().split())
    wanted = {str(x) for x in picked if x}
    matched = []
    for item in SYMPTOMS:
        hit = item["id"] in wanted
        if hay:
            hit = hit or any(key in hay for key in item["keywords"])
        if not hit:
            continue
        matched.append({
            "level": "INFO",
            "section": item["title"],
            "symptomId": item["id"],
            "message": item["blurb"],
            "remedy": item["advice"],
            "guide": item["guide"],
            "also": item.get("also") or "",
            "fixes": item.get("fixes") or {},
        })
    return matched


def _merge_fixes(findings: list[dict[str, Any]]) -> dict[str, Any]:
    remove: list[str] = []
    quirks: dict[str, dict[str, Any]] = {}
    boot_args: list[str] = []
    for item in findings:
        fixes = item.get("fixes") or {}
        for kid in fixes.get("removeKexts") or []:
            if kid not in remove:
                remove.append(kid)
        for group, values in (fixes.get("setQuirks") or {}).items():
            quirks.setdefault(group, {}).update(values)
        for arg in fixes.get("addBootArgs") or []:
            if arg not in boot_args:
                boot_args.append(arg)
    return {"removeKexts": remove, "setQuirks": quirks, "addBootArgs": boot_args}


def run_troubleshoot(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    setup = usb_setup_findings(body)
    matched = _match_symptoms(str(body.get("log") or ""), list(body.get("symptomIds") or []))
    # Prefer setup FAILs first, then matched symptoms, skip duplicate symptomIds of lower severity.
    seen = set()
    findings: list[dict[str, Any]] = []
    for item in setup + matched:
        key = (item.get("symptomId") or item.get("message"), item.get("level"))
        if key in seen:
            continue
        seen.add(key)
        findings.append(item)

    fails = sum(1 for x in findings if x.get("level") == "FAIL")
    warns = sum(1 for x in findings if x.get("level") == "WARN")
    return {
        "success": True,
        "guide": DORTANIA_KERNEL,
        "usbGuide": DORTANIA_USB,
        "findings": findings,
        "fixes": _merge_fixes(findings),
        "summary": (
            f"{fails} blocking USB/config issue(s), {warns} warning(s)."
            if findings
            else "No matching symptom. Paste a verbose line or pick one from Dortania’s kernel list."
        ),
    }
