# Studio profile matrix

Maps `data/profiles/<id>.json` to Dortania pages, required ACPI, extra files, and the traps that break Sequoia.

Legend: **must** = boot fails without it on that generation. **usual** = Dortania default. **machine** = board-specific.

## Intel desktop

| Studio id | CPU | Dortania | SSDTs (must) | Extra notes |
| --- | --- | --- | --- | --- |
| `intel_haswell` | 4xxx | [haswell](https://dortania.github.io/OpenCore-Install-Guide/config.plist/haswell.html) | PLUG, EC | IgnoreInvalidFlexRatio **must**. SMBIOS iMac15,1 / iMac14,4; Ventura+ needs a newer SMBIOS (Kaby). ig-platform-id `0300220D` or compute `04001204` |
| *(Broadwell desktop — no Studio id; share Haswell page)* | 5xxx i5/i7 non-E | same page | PLUG, EC | iMac16,2; ig-platform-id `07002216` |
| `intel_skylake` | 6xxx | [skylake](https://dortania.github.io/OpenCore-Install-Guide/config.plist/skylake.html) | PLUG, EC-USBX | SetupVirtualMap YES. iMac17,1 dropped in Ventura → use Kaby SMBIOS |
| `intel_kaby_lake` | 7xxx | [kaby-lake](https://dortania.github.io/OpenCore-Install-Guide/config.plist/kaby-lake.html) | PLUG, EC-USBX | Last “easy” iGPU SMBIOS for Ventura+ (`iMac18,x`) |
| `intel_coffee_lake` | 8/9xxx | [coffee-lake](https://dortania.github.io/OpenCore-Install-Guide/config.plist/coffee-lake.html) | PLUG, EC-USBX, **AWAC**, **PMC** (true 300-series, not Z370) | Z390: DevirtualiseMmio + ProtectUefiServices. SetupVirtualMap often **NO** on Z390. XHCI-unsupported on H370/B360/H310/Z390 (Mojave-era) |
| `intel_comet_lake` | 10xxx | [comet-lake](https://dortania.github.io/OpenCore-Install-Guide/config.plist/comet-lake.html) | PLUG, EC-USBX, AWAC, **RHUB on Asus 400-series** | SetupVirtualMap **NO**. DevirtualiseMmio + ProtectUefiServices. iMac20,1 / iMac20,2 |
| `intel_rocket_lake` | 11xxx | no first-class Dortania desktop page | treat like Comet + spoof | Community: Comet Lake iGPU spoof / dGPU iMac20,1. CFG-Lock / VT-d same as Comet |

## Intel HEDT / Xeon W

| Studio id | Chipset | Dortania | SSDTs (must) | CPUID / extra |
| --- | --- | --- | --- | --- |
| `intel_haswell_e` | X99 / C612 | [haswell-e](https://dortania.github.io/OpenCore-Install-Guide/config-HEDT/haswell-e.html) | PLUG, EC-USBX, **RTC0-RANGE-HEDT**, **UNC** | Cpuid1Data `C3060300…` Mask `FFFFFFFF…`. AppleXcpmExtraMsrs YES. IgnoreInvalidFlexRatio YES. LegacyOverwrite YES, WriteFlash NO. iMacPro1,1. **Dell T7910: CpuTscSync + TscSyncTimeout, not ResetTSCAdjust.efi** |
| `intel_broadwell_e` | X99 / C612 | [broadwell-e](https://dortania.github.io/OpenCore-Install-Guide/config-HEDT/broadwell-e.html) | same | Cpuid1Data `D4060300…` (not the Haswell-E value). Same Dell TSC notes |
| `intel_skylake_x` | X299 | [skylake-x](https://dortania.github.io/OpenCore-Install-Guide/config-HEDT/skylake-x.html) | PLUG, EC-USBX, RTC0-RANGE-HEDT (no UNC) | No CPUID spoof. RebuildAppleMemoryMap + DevirtualiseMmio + SyncRuntimePermissions. SetupVirtualMap YES except ASUS v3006+. WriteFlash YES. TSCAdjustReset.kext common on X299 |
| `intel_xeon_w_skylake` | C422 / X299 W-21xx | same HEDT page | like Skylake-X | iMacPro1,1 / MacPro7,1. RestrictEvents for RAM popup on MacPro7,1 |
| `intel_xeon_w_cascade` | W-32xx | same | like Cascade-X | AppleMCEReporterDisabler if dual-socket MacPro7,1 panic |

Haswell-E vs Broadwell-E is **CPU SKU**, not chipset. E5 v3 / 58xx/59xxX → Haswell-E spoof. E5 v4 / 68xx/69xxX → Broadwell-E spoof. Dual-socket T7910 with mixed gens is unsupported.

## Intel hybrid (12th+)

| Studio id | CPU | Extra kexts / quirks | SSDTs |
| --- | --- | --- | --- |
| `intel_alder_raptor` | 12/13/14th | **ProvideCurrentCpuInfo YES**, CpuTopologyRebuild, RestrictEvents, often LucyRTL8125 | PLUG-ALT on some boards, EC-USBX, AWAC, RHUB as needed |
| `intel_meteor_lake` | Core Ultra 1 | Experimental. Arrow Lake may need E-cores off; CpuTopologyRebuild still catching up | same family as Alder; verify SSDT-PLUG-ALT |

Dortania’s official picker historically stopped at Comet Lake / Cascade-X. Hybrid guidance is Acidanthera quirk + b00t0x kext + forum.

## AMD

| Studio id | CPU | Dortania | SSDTs | Must |
| --- | --- | --- | --- | --- |
| `amd_zen_legacy` | Zen 1/2, TR 1/2 | [zen](https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html) | EC-USBX; **CPUR only on B550/A520** | DummyPowerManagement, ProvideCurrentCpuInfo, AMD Vanilla patches with **core count hex**, no CPUFriend |
| `amd_ryzen_zen3_4` | Zen 3/4 | same | same | Zen 4: IOPCIFamily patch in Vanilla. PAT patch: Sequoia has its own — do not enable both PAT patches |
| `amd_apu_nooted` | Ryzen APU | zen + NootedRed | EC-USBX ± CPUR | **NootedRed, not WhateverGreen.** iGPU only |

Threadripper 3xxx (39xx) was unsupported; later BIOS + OC claimed support — treat as TRX40: DevirtualiseMmio + KASLR whitelist.

## Other

| Studio id | Notes |
| --- | --- |
| `proxmox_kvm_guest` | VM: SetupVirtualMap often NO (QEMU listed on EXITBS page). ProvideCurrentCpuInfo. No USB map |

## Shared defaults (all UEFI hacks)

Enable unless a platform page says otherwise:

- Booter: AvoidRuntimeDefrag, EnableSafeModeSlide, ProvideCustomSlide (until log says all slides usable)
- Kernel: DisableLinkeditJettison, PanicNoKextDump, PowerTimeoutKernelPanic
- Kernel: AppleXcpmCfgLock if CFG-Lock cannot be disabled (Haswell+)
- Kernel: DisableIoMapper if VT-d cannot be disabled
- UEFI: RequestBootVarRouting, ConnectDrivers YES
- Misc: ScanPolicy 0 for installer USB, SecureBootModel Disabled while installing
- Drivers: OpenRuntime + HFS driver + ResetNvramEntry
- Kexts: Lilu, VirtualSMC, WhateverGreen (or Nooted*), AppleALC

**XhciPortLimit:** Dortania still documents YES for installer on older pages; **macOS 11.3+ panics** (`AppleUSBHostPort::createDevice`) if it is left on. Studio policy: **false** on Big Sur 11.3 and newer. Map USB after install.

## SMBIOS cheat sheet

| Hardware | Typical SMBIOS | Dropped in |
| --- | --- | --- |
| Haswell iGPU only | iMac14,4 | Ventura |
| Haswell + dGPU | iMac15,1 | Ventura |
| Broadwell desktop | iMac16,2 | Ventura |
| Skylake | iMac17,1 | Ventura |
| Kaby / Coffee iGPU | iMac18,1 / 18,3 | — |
| Coffee + dGPU / 9th gen | iMac19,1 | — |
| Comet | iMac20,1 / 20,2 | — |
| No iGPU (X99/X299/Xeon W/HEDT/AMD dGPU) | **iMacPro1,1** or MacPro7,1 | — |
| MacPro7,1 | needs RestrictEvents (`revpatch=sbvmm` etc. as needed) to hide extra RAM DIMM warning | — |

Ventura+ on Haswell/Skylake desktops: spoof a Kaby-or-newer SMBIOS; that does not make a dead iGPU new again — use a supported dGPU.
