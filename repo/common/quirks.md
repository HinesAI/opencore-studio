# Booter, Kernel, UEFI quirks

Paraphrase of Dortania platform pages + Acidanthera Configuration.pdf ideas. Defaults below are “what the generation needs,” not Sample.plist stock (Sample is mostly NO / 0).

`quirkOverrides` in Studio must not wipe a profile-required integer (TscSyncTimeout) back to 0 unless the user did that on purpose.

## Booter → Quirks

| Quirk | Meaning | YES on | NO / careful |
| --- | --- | --- | --- |
| AvoidRuntimeDefrag | Keep UEFI runtime (NVRAM, time) | All UEFI | — |
| EnableSafeModeSlide | slide= in safe mode | All modern | — |
| ProvideCustomSlide | Pick a usable KASLR slide | Until log says all 256 slides usable | Disable when log says so |
| EnableWriteUnprotector | Drop CR0 WP for trampoline | Haswell–Kaby, older OEM without MAT | Conflicts with RebuildAppleMemoryMap on new boards |
| RebuildAppleMemoryMap | macOS-shaped memory map | Coffee+, AMD Zen, X299 | Some laptop OEM; then use WriteUnprotector instead |
| SyncRuntimePermissions | MAT vs runtime RX | With RebuildAppleMemoryMap | — |
| SetupVirtualMap | SetVirtualAddresses fix | Skylake and older; many Gigabyte | Ice Lake, Comet 400, B550/A520/new X570, TRx40, 2020+ X299, QEMU |
| DevirtualiseMmio | Free MMIO for KASLR | Z390, Z490, Ice Lake, TRx40 | **X99 / C612 often breaks** |
| ProtectUefiServices | Stop firmware overriding services | Z390, Ice Lake, VMs | Others NO |
| ProvideMaxSlide | Cap slide | Rare | 0 default |
| ResizeAppleGpuBars | Shrink BAR for macOS | `0` if Resizable BAR enabled in BIOS | `-1` disable |
| FixupAppleEfiImages | boot.efi image fix | Sample often YES now | Leave unless a guide says |
| ForceExitBootServices | Old Aptio | Almost never | Can hide real bugs |

EXITBS at Start: first toggle SetupVirtualMap, then the WriteUnprotector / Rebuild pair, then DevirtualiseMmio.

## Kernel → Quirks

| Quirk | Meaning | YES on | Notes |
| --- | --- | --- | --- |
| AppleCpuPmCfgLock | Patch AICPM CFG-Lock | Ivy and older; 10.10- on Broadwell- | Haswell+ uses Xcpm variant |
| AppleXcpmCfgLock | Patch XCPM CFG-Lock | Haswell+ if CFG-Lock stuck ON | Disable if BIOS CFG-Lock is off |
| AppleXcpmExtraMsrs | Hide extra MSRs | **Broadwell-E and older Xeon/Pentium** | **NO on Skylake-X** per Haswell-E vs Skylake-X pages |
| AppleXcpmForceBoost | Force turbo | Rare debug | — |
| DisableIoMapper | Ignore VT-d DMAR | If VT-d cannot be disabled | Prefer BIOS VT-d off |
| DisableIoMapperMapping | 13.3+ VT-d map | Some 12th+ with VT-d on | — |
| DisableLinkeditJettison | Keep __LINKEDIT | All modern | Lilu wants this |
| DisableRtcChecksum | Skip Apple RTC checksum | Some HWs that reset NVRAM | Optional |
| DummyPowerManagement | Skip AICPM | **All AMD** | Never on Intel with working XCPM |
| LapicKernelPanic | HP / laptops APIC | Some HP | Desktop NO |
| PanicNoKextDump | Keep panic log | All while installing | — |
| PowerTimeoutKernelPanic | 10.15 power timeout | All modern | Dortania YES on HEDT |
| ProvideCurrentCpuInfo | Topology / AMD patches | **AMD Zen, Alder/Raptor** | Required for AMD Vanilla |
| ThirdPartyDrives | SATA trim | Intel SSD on non-Apple | Optional |
| XhciPortLimit | Patch 15-port limit | **Do not use on 11.3+** | Map USB instead |
| CustomSMBIOSGuid | Dell/VAIO SMBIOS inject | Rare OEM | — |
| SetApfsTrimTimeout | APFS trim | `-1` default | — |

### Kernel → Emulate

| Key | Use |
| --- | --- |
| Cpuid1Data / Cpuid1Mask | Haswell-E `C3060300` / Broadwell-E `D4060300` + mask `FFFFFFFF 00000000 00000000 00000000` |
| DummyPowerManagement | Duplicate of quirk for some samples — AMD only |
| MaxKernel / MinKernel | Limit spoof to certain OS |

Leave blank on Skylake-X and desktop Skylake+.

## UEFI → Quirks

| Quirk | Meaning | YES on |
| --- | --- | --- |
| RequestBootVarRouting | Redirect boot vars via OC | All |
| IgnoreInvalidFlexRatio | MSR_FLEX_RATIO 0x194 | **Pre-Skylake** including Haswell-E / Broadwell-E |
| ReleaseUsbOwnership | Take USB from firmware | Installer USB issues, many desktops |
| UnblockFsConnect | HP firmware blocks scans | Some HP |
| EnableVectorAcceleration | AES accel | Modern YES in Sample |
| EnableVmx | Nested VT-x | VMs / Hypervisor.framework guests |
| ExitBootServicesDelay | ms delay | 0 unless old Insyde |
| ForgeUefiSupport | Pre-UEFI 2.0 | Legacy only |
| ReloadOptionRoms | GPU ROM | Rare |
| ResizeGpuBars | firmware BAR | `-1` |
| TscSyncTimeout | µs wait for TSC rendezvous | **Dell C612: 500000–1000000**. 0 = off. Does not replace a TSC kext for S3 |
| DisableSecurityPolicy | Surface / MS | Only those |

## NVRAM

| Key | Haswell-E / Broadwell-E | Skylake-X / modern |
| --- | --- | --- |
| LegacyOverwrite | YES | NO |
| WriteFlash | NO | YES |
| boot-args | `-v keepsyms=1 debug=0x100 alcid=1` plus GPU args | same |
| csr-active-config | 00000000 SIP on; installer often left default | — |
| prev-lang:kbd | `en-US:0` | — |

## Misc → Boot / Security (installer)

- ShowPicker true, Timeout 5
- HideAuxiliary **false** when you need Reset NVRAM visible without Spacebar (T7910 text picker)
- PickerMode External only with OpenCanopy + Resources; otherwise Builtin
- ScanPolicy 0
- SecureBootModel Disabled until post-install
- Vault Optional
- AllowSetDefault true

## DeviceProperties

Delete Sample.plist audio PciRoot unless you inject layout-id there. Prefer `alcid=` in boot-args.

iGPU: `AAPL,ig-platform-id` as DATA (bytes reversed vs the hex Dortania shows in tables). WhateverGreen docs: desktop Haswell `0300220D` → bytes `0D 22 00 03`.
