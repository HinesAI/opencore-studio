# Troubleshooter map

Input: verbose log snippet, OpenCore debug log, or a human description. Output: section to change, files to add/remove, Studio profile action.

Use with `engine/troubleshooter.py`. New rows here should become `SYMPTOMS` entries after the T7910 case is proven.

HaltLevel: OpenCore stops on ERROR. A **missing enabled UEFI driver** is an ERROR. That is why ResetTSCAdjust.efi halted the T7910 rebuild.

## OpenCore / picker (before macOS)

| Symptom | Likely cause | Do this |
| --- | --- | --- |
| `OCB: Failed to load driver … Not Found` then halt | UEFI → Drivers lists a file not in `EFI/OC/Drivers` | Delete or disable the entry. Do not ship ResetTSCAdjust.efi on OC 1.0.x |
| `OCS: No schema for …` / `Missing key` | plist from a configurator or mixed OC versions | Rebuild from Sample of the **same** OC tag as `OpenCore.efi` |
| `OC: Failed to load OpenCore image` / `StartImage failed` | firmware memory map after CPU/RAM change (Dell T5810 tip) | Toggle Above 4G and/or Legacy Option ROMs once to force a map rebuild |
| Picker never shows | ShowPicker false, Timeout 0, or OpenCanopy without Resources | Text picker first (`PickerMode=Builtin` or External only with Resources) |
| No Reset NVRAM | HideAuxiliary true; ResetNvramEntry not enabled | Enable driver; HideAuxiliary false **or** press Spacebar |
| ScanPolicy hides installer | ScanPolicy not 0 | Misc → Security → ScanPolicy = 0 |
| `LoadImage failed - Security Violation` | SecureBootModel / Vault | SecureBootModel Disabled for install; Vault Optional |

## Stuck at `[EB|#LOG:EXITBS:START]`

Split the same way Dortania does.

**Booter**

- Enable SetupVirtualMap on Z390-and-older **except** when the board is in the “breaks with it” list: Ice Lake, Comet Lake 400-series, AMD B550/A520/new X570, TRx40, many 2020+ X299, QEMU.
- RebuildAppleMemoryMap vs EnableWriteUnprotector: newer platforms use Rebuild + SyncRuntimePermissions and **disable** WriteUnprotector. OEM MAT-less firmware: reverse that pair.
- DevirtualiseMmio: YES on Z390 / Z490 / Ice Lake / TRx40. **NO on X99** (breaks some C612). TRx40 also needs MmioWhitelist (KASLR guide).

**Kernel patches (AMD)**

- ProvideCurrentCpuInfo must be YES.
- Four `Force cpuid_cores_per_package` patches must use **physical core count in hex** (6-core = `06`, 8 = `08`, 16 = `10`, 32 = `20`).
- DummyPowerManagement YES. Do not use CPUFriend on AMD.

**UEFI**

- UnblockFsConnect on some HP.
- ProvideConsoleGop YES if GOP dies at handoff.

## Early kernel / ACPI / clocks

| Symptom | Cause | Fix |
| --- | --- | --- |
| Panic **Non-monotonic time** | TSC desync (Dell C612, some X299) | **Not EXITBS.** CpuTscSync.kext after Lilu + UEFI TscSyncTimeout 500000. Do not add missing ResetTSCAdjust.efi. Older workaround: `cpus=1` |
| Panic **IOPCIFamily** on X99 | uncore bridges | SSDT-UNC.aml. Disable DevirtualiseMmio |
| Halt on RTC / HPET / PCI Configuration Begins | AWAC or RTC range | Desktop 300/400: SSDT-AWAC (or SSDT-RTC0). HEDT: SSDT-RTC0-RANGE-HEDT |
| Stuck ACPI on B550 | CPU devices | SSDT-CPUR.aml (B550/A520 only) |
| `Wrong CD Clock Frequency` Ice Lake | iGPU clock | Ice Lake WhateverGreen / boot-args from Dortania laptop Ice Lake page |
| `AppleIntelMCEReporter` | MacPro7,1 / dual CPU | AppleMCEReporterDisabler.kext |
| `AppleIntelCPUPowerManagement` panic | AICPM on AMD or old Intel | AMD: DummyPowerManagement. Intel Ivy-: AppleCpuPmCfgLock |

## USB / disk

| Symptom | Cause | Fix |
| --- | --- | --- |
| Waiting for Root Device / prohibited | USB ownership or 15-port limit | USB 2 vs 3 port; XHCI Hand-off; ReleaseUsbOwnership YES; **no generic USB map on installer**; Ice Lake/Comet Asus/AMD: SSDT-RHUB |
| `AppleUSBHostPort::createDevice` reboot loop (11.3+) | XhciPortLimit still true | Kernel → XhciPortLimit **false**. Remove USBInjectAll / USBToolBox+UTBMap from installer |
| USB kext wasn't loaded | UTBMap not on the stick | Leave USBToolBox/UTBMap off until mapped on the target PC |
| X99 USB 3 missing | unsupported XHCI | XHCI-unsupported.kext (Dortania gathering-files: X79/X99) plus a real map later |
| NVMe invisible | missing NVMe in firmware | NvmExpressDxe.efi only if firmware has no NVMe; else NVMeFix for PM |

## GPU / display

| Symptom | Cause | Fix |
| --- | --- | --- |
| Black after `gIOScreenLock` / `gIOLockState` on Navi | AGDP board-id | `agdpmod=pikera` (RX 5000/6000 **only**, not Polaris/Vega) |
| Navi still black | wrong framebuffer / CSM | UEFI GOP, CSM off, try another DP/HDMI |
| WhateverGreen + NootedRed together | conflict | APU: NootedRed only. dGPU: WhateverGreen only. NootRX: no WEG |
| Intel iGPU panic | bad ig-platform-id | Haswell `0300220D` display / `04001204` compute. Broadwell `07002216`. `-igfxvesa` to prove it is framebuffer |
| NVIDIA on Monterey+ | no drivers | Replace GPU. Kepler died in Monterey |
| RX 6700 / 6700 XT | Navi 22 unsupported | NootRX (experimental) or different card |

## SMBIOS / security / kext load

| Symptom | Cause | Fix |
| --- | --- | --- |
| This version of Mac OS X is not supported: Reason Mac… | SMBIOS too old | iMac18,x+ for Ventura; iMac20,x Comet; iMacPro1,1 HEDT/AMD |
| Plist only kext has CFBundleExecutable | USBMap with leftover executable key | Empty ExecutablePath |
| Cannot perform kext summary | order / dup plugins | Lilu then plugins; one VoodooInput |
| kextd stall AppleACPICPU | missing SMC | Lilu + VirtualSMC, not both VirtualSMC and FakeSMC |
| cckprngintgen | entropy / VirtualSMC | VirtualSMC present and first plugin after Lilu |
| ramrod / Forcing CS_RUNTIME | Big Sur+ snapshot / SIP | follow Dortania ramrod section; usually USB or SecureBootModel |

## AMD-only extras

- `X64 Exception Type` on FX: 15h/16h patches / XLNCUSBFix.
- MSI A520/B550/X570 Monterey+: Vanilla IOPCIFamily patch (same one Zen 4 needs).
- Two PAT patches: enable **one** (Sequoia-specific **or** legacy), never both.

## T7910 / T5810 short path

1. Profile: `intel_haswell_e` (E5 v3) or `intel_broadwell_e` (E5 v4).
2. CPUID spoof matching the SKU.
3. SSDT-PLUG, EC-USBX, RTC0-RANGE, UNC.
4. IgnoreInvalidFlexRatio, AppleXcpmExtraMsrs, AppleXcpmCfgLock if CFG-Lock on.
5. CpuTscSync.kext + TscSyncTimeout 500000.
6. OpenRuntime, OpenHfsPlus (or HfsPlus), ResetNvramEntry — **only files that exist**.
7. iMacPro1,1 or MacPro7,1, discrete AMD GPU, `agdpmod=pikera` if Navi.
8. IntelMausi, AppleALC (T5810 reports layout 17 — verify on T7910).
9. Installer: no UTBMap. After install: map USB on **this** chassis (front panel is proprietary).
10. Dual-socket: cap at 64 threads; AppleMCEReporterDisabler if MacPro7,1 panics.

If it still panics Non-monotonic time with CpuTscSync loaded: confirm Lilu is first, kext is in Kernel → Add Enabled, and try `TscSyncTimeout=1000000`. Last resort `cpus=1` to prove TSC, then fix kext order.

## Suggested Studio `SYMPTOMS` ids (not all wired yet)

`missing_uefi_driver`, `non_monotonic_time`, `exitbs_start`, `waiting_root_device`, `appleusbhostport`, `iopcifamily_x99`, `awac_rtc`, `navi_black`, `mce_reporter`, `smbios_unsupported`, `kextd_stall_smc`, `secure_boot`, `amd_core_count`, `hybrid_topology`.
