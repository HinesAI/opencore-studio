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

## Layout

| Path | Role |
| --- | --- |
| `app.py` | Zero-dependency Python API + static UI |
| `engine/` | Plist build/import, hardware match, kexts, SMBIOS, EFI, USB, updater |
| `static/` | Dark studio UI (HTML / CSS / JS) |
| `data/` | Sample.plist, AMD patches, CPU/GPU catalogs, hardware profiles |
| `macos-native/main.swift` | AppKit + WKWebView host |
| `build-macos-native.sh` | Sync into the `.app` and compile Swift |

## Notes

- Built `.app` bundles, EFI output, and download caches are not in git. Rebuild locally.
- USB erase requires an explicit `confirm=ERASE` and never targets internal disks.
- Putting a full macOS installer onto the same stick (`createinstallmedia` + EFI on the ESP) is not in yet.

Hackintosh work can brick a machine or violate Apple’s terms. Use at your own risk.
