# OpenCore Studio — Mac Pro Workstation Package

Welcome to **OpenCore Studio**, an automated OpenCore EFI and `config.plist` generation and tuning platform packaged specifically for macOS.

---

## 🚀 Quick Start on Your Mac Pro

### Method 1: Double-Click & Run Immediately (No Compilation Needed)
The `.app` bundle is pre-configured and ready to run immediately using macOS default tools:
1. Extract the archive:
   ```bash
   tar -xzvf opencore-studio-macpro.tar.gz
   cd opencore-studio
   ```
2. Double-click **`macos-dist/OpenCore Studio.app`** in Finder, or in Terminal run:
   ```bash
   open "macos-dist/OpenCore Studio.app"
   ```
3. To install it to your Applications folder:
   ```bash
   cp -R "macos-dist/OpenCore Studio.app" /Applications/
   ```

---

### Method 2: Compile the 100% Native Cocoa / WebKit Binary
If you want OpenCore Studio to run in its own dedicated native macOS window with Cocoa menus, traffic lights, and native AppKit lifecycle management:
1. Ensure Xcode Command Line Tools are installed:
   ```bash
   xcode-select --install
   ```
2. Run the included native build script:
   ```bash
   cd opencore-studio
   ./build-macos-native.sh
   ```
This invokes Apple's native `swiftc` compiler on `macos-native/main.swift` and embeds the Mach-O binary directly into `OpenCore Studio.app/Contents/MacOS/OpenCoreStudioNative`.

---

## 🛠 Project Components
- **`app.py`**: Zero-dependency Python backend server exposing REST endpoints for profile generation, kext topological sorting, and Apple XML serialization.
- **`engine/`**:
  - `plist_builder.py`: Builds compliant Apple XML `config.plist` from official `Sample.plist`.
  - `validator.py`: Pre-flight sanity check engine detecting bootloops, missing kexts, and bad quirks.
  - `amd_patcher.py`: Automatic hex core-count calculation for AMD Ryzen AM4/AM5.
  - `smbios.py`: GenSMBIOS-style authentic serial number, MLB, UUID, and ROM generator.
  - `kext_manager.py`: Enforces Lilu index 0, VirtualSMC ahead of plugins, and manages repos.
  - `profiles.py`: Hardware profiles loader with dynamic remote manifest importer.
- **`data/`**: Canonical `Sample.plist`, AMD Vanilla patches, 26 curated kexts, and 5 hardware profiles (Comet Lake, Alder/Raptor Lake, Coffee Lake, AMD Ryzen, Proxmox VM).
- **`macos-native/main.swift`**: Native Swift AppKit wrapper embedding `WKWebView` and controlling the Python backend lifecycle.

---

## 🤖 Instructions for AI Agents / Cursor on Mac Pro
Refer to **`MACPRO-TAKEOVER-CONTEXT.txt`** for the complete technical handover specification, API contract, and plist invariants.
