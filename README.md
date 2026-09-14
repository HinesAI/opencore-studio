# OpenCore Studio

A native macOS studio for building and revising OpenCore `config.plist` files, then assembling an EFI folder you can copy to a USB stick.

Type a CPU (W-2133, i7-10700K, 5900X), pick a GPU family, choose kexts and SMBIOS, and Studio writes a Sample.plist-based config instead of a hand-edited XML tree. Load an existing `config.plist` to keep editing.

**Requires:** macOS with Python 3 and Xcode Command Line Tools. No pip packages.

## What it does

- Hardware wizard that maps CPU/GPU models onto architecture profiles
- Guided steps: hardware → kexts → quirks / boot-args → SMBIOS → review → EFI / USB
- Load and export `config.plist` (XML or binary) from the native window
- Switch OpenCore Sample versions (included, latest, or older GitHub RELEASE)
- Pull Acidanthera Sample.plist, AMD Vanilla patches, and kext release tags
- Build an EFI folder and copy it to an external USB (internal disks are blocked)
- Monterey+ installer catalog and `InstallAssistant.pkg` download (resume / cancel)

SMBIOS values are generated for Apple services compatibility. You still own the result — review the plist before you boot it.

## Run it

Build the native app, then open it. Do not use Chrome against the Python server; the Swift window is the UI.

```bash
xcode-select --install   # once
./build-macos-native.sh
open "macos-dist/OpenCore Studio.app"
```

First launch seeds Application Support, then asks which OpenCore version to apply. Caches, installer downloads, and update state live in `~/Library/Application Support/OpenCore Studio`.

## Share between Macs

GitHub is the repo. Use rsync when you want EFI / `config.plist` (and a live source tree) on another Mac or a USB/NAS folder:

```bash
./sync-share.sh init          # creates share/remote.conf
# edit share/remote.conf — default is /Volumes/tools/OpenCoreStudioShare
./sync-share.sh push          # this Mac -> share
./sync-share.sh pull          # share -> this Mac
./sync-share.sh export-efi    # copy the last EFI build into share/efi
./sync-share.sh push efi
```

For SSH, set `REMOTE=user@other-mac.local` and `REMOTE_PATH=/path/on/that/mac`. Pull/push never delete extra files on the other side unless you add that later.

## Layout

| Path | Role |
| --- | --- |
| `app.py` | Zero-dependency Python API + static UI |
| `engine/` | Plist build/import, hardware match, kexts, SMBIOS, EFI, USB, updater |
| `static/` | Dark studio UI (HTML / CSS / JS) |
| `data/` | Sample.plist, AMD patches, CPU/GPU catalogs, hardware profiles |
| `macos-native/main.swift` | AppKit + WKWebView host |
| `build-macos-native.sh` | Sync into the `.app` and compile Swift |

## Credits / third-party

OpenCore Studio is the GUI, hardware wizard, plist import/export, and EFI/USB assembly flow. It is **not** OpenCore and does not replace it.

Upstream projects this app ships, downloads, or follows:

| Project | Who | How Studio uses it |
| --- | --- | --- |
| [OpenCore](https://github.com/acidanthera/OpenCorePkg) and [Sample.plist](https://github.com/acidanthera/OpenCorePkg) | [Acidanthera](https://github.com/acidanthera) | Bundled Sample schema; RELEASE zip cached when you pick a version or build EFI (BSD 3-Clause) |
| Lilu, VirtualSMC, WhateverGreen, AppleALC, IntelMausi, NVMeFix, and other Acidanthera kexts | Acidanthera | Downloaded from their GitHub releases when you build EFI |
| [AMD Vanilla](https://github.com/AMD-OSX/AMD_Vanilla) | AMD-OSX / community | Kernel patches in `data/amd_patches.plist` for Ryzen configs |
| [OcBinaryData](https://github.com/acidanthera/OcBinaryData) | Acidanthera | Resources fetched when assembling EFI |
| Ethernet, Wi-Fi, USB, and Nooted kexts | Mieze, OpenIntelWireless, USBToolBox, ChefKissInc, and others listed in `data/kexts.json` | Downloaded from each author’s GitHub releases |
| [OpenCore Install Guide](https://dortania.github.io/OpenCore-Install-Guide/) | [Dortania](https://github.com/dortania) | Quirk / kext / profile recommendations follow their docs |
| macOS `InstallAssistant.pkg` catalog | Apple | Public sucatalog only; installers are Apple’s |

Those authors keep their copyrights and licenses. Keep their notices if you redistribute files they published. Issues with OpenCore or a kext belong on that project’s tracker, not here.

## Notes

- Built `.app` bundles, EFI output, and download caches are not in git. Rebuild locally.
- USB erase requires an explicit `confirm=ERASE` and never targets internal disks.
- Putting a full macOS installer onto the same stick (`createinstallmedia` + EFI on the ESP) is not in yet.

Hackintosh work can brick a machine or violate Apple’s terms. Use at your own risk.
