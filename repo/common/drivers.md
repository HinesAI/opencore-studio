# UEFI drivers

`config.plist` → UEFI → Drivers is **not** a folder listing. OpenCore loads only Enabled rows. Each Path is a file in `EFI/OC/Drivers`.

## Minimum working set (UEFI PC, Sequoia installer)

1. `OpenRuntime.efi` — required
2. HFS driver — `HfsPlus.efi` (OcBinaryData) or `OpenHfsPlus.efi` (OpenCorePkg)
3. `ResetNvramEntry.efi` — picker Reset NVRAM

ConnectDrivers: YES.

LoadEarly: **false** for these. LoadEarly true is for `OpenVariableRuntimeDxe.efi` (emulated NVRAM) **before** OpenRuntime.

## Optional

| Driver | When |
| --- | --- |
| OpenCanopy.efi | GUI picker; same OC build; Resources present |
| AudioDxe.efi | Chime; not AppleALC |
| FirmwareSettingsEntry.efi | Reboot to setup |
| OpenNtfsDxe / Ext4Dxe | See other OS volumes |
| NvmExpressDxe | Firmware without NVMe |
| OpenUsbKbDxe | **Legacy CSM/Duet only** — breaks many UEFI boards |

## Forbidden / halt risks

- Any Path whose file was not copied (T7910 ResetTSCAdjust.efi)
- Clover drivers: AptioMemoryFix, OsxAptioFix, EmuVariableUEFI
- Both HfsPlus and OpenHfsPlus enabled
- OpenCanopy from a different OC version than OpenCore.efi

## ResetTSCAdjust.efi (historical)

T5810 GitHub EFIs add it as a **Driver** (not a Tool) so it runs every boot before macOS. Author: denskop (comment on VoodooTSCSync#1). **Not in OpenCore 1.0.6/1.0.7 zips.** Studio 1.2 path: CpuTscSync.kext + TscSyncTimeout. If we later vendor a known-good denskop EFI, it must be copied into Drivers *before* enabling it.
