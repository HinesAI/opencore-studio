# File locations

Every extra binary Studio or a human EFI builder might need, and **where it actually lives**. Paths are relative to an OpenCore EFI folder unless noted.

Convention: **list a driver in `config.plist` → UEFI → Drivers only if the file is on disk under `EFI/OC/Drivers/`.** Missing enabled drivers halt OpenCore.

Compiled SSDTs downloaded from Dortania often have longer names (`SSDT-PLUG-DRTNIA.aml`). Studio aliases them to the short names Dortania uses in the config pages. See `engine/efi_builder.py` `SSDT_ALIASES`.

## OpenCorePkg RELEASE zip

Download: `https://github.com/acidanthera/OpenCorePkg/releases/download/<tag>/OpenCore-<tag>-RELEASE.zip`

Inside the zip use the **X64** tree (IA32 is 32-bit):

| Zip path | Goes to | Notes |
| --- | --- | --- |
| `X64/EFI/BOOT/BOOTx64.efi` | `EFI/BOOT/` | Required |
| `X64/EFI/OC/OpenCore.efi` | `EFI/OC/` | Required |
| `X64/EFI/OC/Drivers/*.efi` | `EFI/OC/Drivers/` | Full set ships here; only *enable* what you need |
| `X64/EFI/OC/Tools/*.efi` | `EFI/OC/Tools/` | Picker tools, not auto-run |
| `Docs/Sample.plist` | renamed to `EFI/OC/config.plist` then edited | Never boot Sample as-is |

### Drivers that ship in OpenCorePkg (enable subset)

| File | Typical use | Enable on T7910? |
| --- | --- | --- |
| `OpenRuntime.efi` | Required runtime | Yes |
| `OpenHfsPlus.efi` | Open-source HFS+; slower than Apple HfsPlus | Studio uses this today |
| `ResetNvramEntry.efi` | Reset NVRAM from picker | Yes (HideAuxiliary off so it is visible) |
| `OpenCanopy.efi` | GUI picker | Optional; needs OcBinaryData Resources, same OC build |
| `AudioDxe.efi` | UEFI boot chime only, not macOS audio | Optional |
| `OpenUsbKbDxe.efi` | Legacy / Duet keyboards | **No** on UEFI Dell |
| `OpenPartitionDxe.efi` | 10.7–10.9 recovery | No for Sequoia |
| `OpenNtfsDxe.efi` / `Ext4Dxe.efi` | Dual-boot volumes | Optional |
| `NvmExpressDxe.efi` | Only if firmware has no NVMe | Usually no on T7910 |
| `XhciDxe.efi` / `UsbMouseDxe.efi` | Legacy USB | No on modern UEFI |
| `FirmwareSettingsEntry.efi` | Reboot to firmware settings | Optional |
| `ToggleSipEntry.efi` | SIP toggle in picker | Optional |

**Not in OpenCore 1.0.6 / 1.0.7 RELEASE Tools or Drivers:** `ResetTSCAdjust.efi`. Listing it anyway is a halt. Use CpuTscSync.kext instead (see below). Older T5810 GitHub EFIs still copy a denskop build of that EFI into Drivers.

### Tools that ship in OpenCorePkg (Misc → Tools, not Drivers)

`OpenShell.efi`, `CleanNvram.efi`, `ResetSystem.efi`, `ControlMsrE2.efi`, `RtcRw.efi`, plus testers. These do **not** run unless chosen in the picker (or enabled as Tools entries). CleanNvram is the old NVRAM reset; prefer `ResetNvramEntry.efi` as a Driver on OC 0.8.4+.

## OcBinaryData

Repo: https://github.com/acidanthera/OcBinaryData  
Zip used by Studio: `https://github.com/acidanthera/OcBinaryData/archive/refs/heads/master.zip`

| Path in repo | Destination | Why |
| --- | --- | --- |
| `Resources/` | `EFI/OC/Resources/` | OpenCanopy icons/fonts/audio |
| `Drivers/HfsPlus.efi` | `EFI/OC/Drivers/` | Apple HFS+; Dortania prefers this over OpenHfsPlus |
| `Drivers/HfsPlusLegacy.efi` | Drivers | Older CPUs without SSE4.2 |
| `Drivers/ExFatDxe.efi` | Drivers | Optional |
| `Drivers/ext4_x64.efi` | Drivers | Optional Linux |
| `Drivers/apfs_aligned.efi` | Drivers | Rare APFS cases |

Do not enable both `HfsPlus.efi` and `OpenHfsPlus.efi`.

## Prebuilt SSDTs (Dortania ACPI)

Base URL:

`https://raw.githubusercontent.com/dortania/Getting-Started-With-ACPI/master/extra-files/compiled/<filename>`

| Config name (ACPI → Add Path) | File on GitHub | Platforms |
| --- | --- | --- |
| `SSDT-PLUG.aml` | `SSDT-PLUG-DRTNIA.aml` | Haswell+ Intel XCPM |
| `SSDT-EC.aml` | `SSDT-EC-DESKTOP.aml` or `SSDT-EC.aml` | Pre-Skylake desktop |
| `SSDT-EC-USBX.aml` | `SSDT-EC-USBX-DESKTOP.aml` | Skylake+ desktop, HEDT, AMD |
| `SSDT-EC-USBX.aml` (laptop) | `SSDT-EC-USBX-LAPTOP.aml` | Laptops |
| `SSDT-AWAC.aml` | `SSDT-AWAC.aml` / `SSDT-AWAC-DISABLE.aml` | 300-series RTC |
| `SSDT-RTC0.aml` | `SSDT-RTC0.aml` | When AWAC SSDT is wrong (no legacy RTC) |
| `SSDT-PMC.aml` | `SSDT-PMC.aml` | True 300-series NVRAM (not Z370) |
| `SSDT-RHUB.aml` | `SSDT-RHUB.aml` | Asus 400-series, Ice Lake, AMD USB reset |
| `SSDT-IMEI.aml` | `SSDT-IMEI.aml` | Sandy-on-7-series / Ivy-on-6-series |
| `SSDT-PNLF.aml` | `SSDT-PNLF.aml` | Laptop / AIO backlight |
| `SSDT-GPI0.aml` | various | Laptop I2C trackpad stub |
| `SSDT-RTC0-RANGE.aml` | **`SSDT-RTC0-RANGE-HEDT.aml`** | X99 / X299 Big Sur+ RTC holes |
| `SSDT-UNC.aml` | `SSDT-UNC.aml` | X99 uncore bridges (IOPCIFamily) |
| `SSDT-CPUR.aml` | `SSDT-CPUR.aml` | AMD B550 / A520 only |
| `SSDT-SBUS-MCHC.aml` | OpenCorePkg AcpiSamples | SMBus / MCHC, post-install |

Sources also live as `.dsl` in `OpenCorePkg/Docs/AcpiSamples/Source/` if you need to retarget ACPI paths.

## Kexts (GitHub RELEASE zips)

Place under `EFI/OC/Kexts/` and list under Kernel → Add. Lilu always first.

| Kext | GitHub | Bundle | Notes |
| --- | --- | --- | --- |
| Lilu | acidanthera/Lilu | `Lilu.kext` | Required |
| VirtualSMC | acidanthera/VirtualSMC | `VirtualSMC.kext` + plugins in same zip | Not FakeSMC |
| SMCProcessor | same zip | `SMCProcessor.kext` | Intel temps |
| SMCSuperIO | same zip | `SMCSuperIO.kext` | Fans |
| SMCBatteryManager | same zip | `SMCBatteryManager.kext` | Laptops |
| SMCDellSensors | same zip | `SMCDellSensors.kext` | Dell SMM fans |
| WhateverGreen | acidanthera/WhateverGreen | `WhateverGreen.kext` | All dGPU/iGPU except Nooted* |
| AppleALC | acidanthera/AppleALC | `AppleALC.kext` | `alcid=` boot-arg |
| IntelMausi | acidanthera/IntelMausi | `IntelMausi.kext` | Intel GbE (T7910 onboard) |
| NVMeFix | acidanthera/NVMeFix | `NVMeFix.kext` | Third-party NVMe |
| RestrictEvents | acidanthera/RestrictEvents | `RestrictEvents.kext` | MacPro7,1 RAM popup; CPU name; VMM |
| CpuTscSync | acidanthera/CpuTscSync | `CpuTscSync.kext` | **T7910 / T5810 Sequoia TSC.** Lilu plugin. Monterey+ writes 0 to IA32_TSC_ADJUST |
| FeatureUnlock | acidanthera/FeatureUnlock | `FeatureUnlock.kext` | Sidecar/AirPlay on unsupported SMBIOS |
| HibernationFixup | acidanthera/HibernationFixup | | Optional |
| BlueToolFixup | acidanthera/BrcmPatchRAM | | Monterey+ BT |
| AirportBrcmFixup | acidanthera/AirportBrcmFixup | | Broadcom Wi-Fi |
| CpuTopologyRebuild | b00t0x/CpuTopologyRebuild | | Alder/Raptor + ProvideCurrentCpuInfo |
| NootedRed | ChefKissInc/NootedRed | | AMD APU iGPU; **no WhateverGreen** |
| NootRX | ChefKissInc/NootRX | | RX 6700 class; **no WhateverGreen** |
| LucyRTL8125Ethernet | Mieze/LucyRTL8125Ethernet | | 2.5G Realtek |
| RealtekRTL8111 | Mieze/RealtekRTL8111-Binary | | RTL8111/8168 |
| AtherosE2200Ethernet | Mieze/AtherosE2200Ethernet | | Killer E22xx |
| AirportItlwm | OpenIntelWireless/itlwm | pick macOS-version zip | Intel Wi-Fi native stack |
| itlwm | same | | Alternate Intel Wi-Fi (Heliport) |
| IntelBluetoothFirmware | OpenIntelWireless/IntelBluetoothFirmware | | Intel BT firmware |
| USBToolBox | USBToolBox/kext | `USBToolBox.kext` | Needs a **board-specific** `UTBMap.kext` |
| UTBMap | generated on the machine | `UTBMap.kext` | **Never ship a generic map** |
| USBInjectAll | Sniki/OS-X-USB-Inject-All | | Mapping aid on Coffee Lake and older Intel only |
| AppleMCEReporterDisabler | various GitHub gists / Acidanthera notes | | Dual-socket / MacPro7,1 MCE panic |
| TSCAdjustReset | interferenc/TSCAdjustReset | kext | X299 Skylake-X alternative; older than CpuTscSync |
| VoodooTSCSync | denskop/VoodooTSCSync | kext | Match IOCPUNumber; last-resort |
| AMD Vanilla patches | AMD-OSX/AMD_Vanilla | not a kext | Kernel → Patch plist; `data/amd_patches.plist` in Studio |
| XLNCUSBFix | Dortania kernel-issues | kext | AMD 15h/16h USB only |

Release assets are almost always `*-RELEASE.zip`. Prefer RELEASE over DEBUG for USB sticks.

## Misc tools (not in EFI, used to *build* files)

| Tool | URL | Output |
| --- | --- | --- |
| ProperTree | https://github.com/corpnewt/ProperTree | plist edits / OC snapshot |
| GenSMBIOS | https://github.com/corpnewt/GenSMBIOS | serial / MLB / UUID / ROM |
| SSDTTime | https://github.com/corpnewt/SSDTTime | USB Reset → SSDT-RHUB, EC, PNLF, etc. |
| USBMap | https://github.com/corpnewt/USBMap | `USBMap.kext` |
| USBToolBox (Windows/macOS mapper) | https://github.com/USBToolBox/tool | `UTBMap.kext` |
| MaciASL | Acidanthera | compile `.dsl` → `.aml` |
| gfxutil | Acidanthera | PciRoot paths for DeviceProperties |
| OCAuxiliaryTools | https://github.com/ic005k/OCAuxiliaryTools | GUI; do not treat as source of truth |

## EFI folder layout (what OpenCore actually reads)

```
EFI/
  BOOT/BOOTx64.efi
  OC/
    OpenCore.efi
    config.plist
    ACPI/*.aml          ← must match ACPI → Add
    Drivers/*.efi       ← must match UEFI → Drivers (enabled)
    Kexts/*.kext        ← must match Kernel → Add (enabled)
    Tools/*.efi         ← must match Misc → Tools if you want picker entries
    Resources/          ← OpenCanopy
```

Kexts that are **plist-only** (USBMap, UTBMap, some injectors) must have **empty** `ExecutablePath` in Kernel → Add. A `CFBundleExecutable` with no binary is the "Plist only kext has CFBundleExecutable" halt.
