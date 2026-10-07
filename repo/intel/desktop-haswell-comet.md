# Intel desktop — Haswell through Comet Lake

Canonical pages:

- https://dortania.github.io/OpenCore-Install-Guide/config.plist/haswell.html
- https://dortania.github.io/OpenCore-Install-Guide/config.plist/skylake.html
- https://dortania.github.io/OpenCore-Install-Guide/config.plist/kaby-lake.html
- https://dortania.github.io/OpenCore-Install-Guide/config.plist/coffee-lake.html
- https://dortania.github.io/OpenCore-Install-Guide/config.plist/comet-lake.html

Studio: `intel_haswell`, `intel_skylake`, `intel_kaby_lake`, `intel_coffee_lake`, `intel_comet_lake`.

## BIOS (all of these)

Disable: Fast Boot, Secure Boot, CSM, Serial/COM, Intel SGX, CFG-Lock if the switch exists.  
Enable: VT-x, Above 4G, EHCI/XHCI Hand-off, AHCI.  
VT-d: off, or leave on and DisableIoMapper.

## Quirk delta (desktop)

| Quirk | Haswell/BDW | Skylake/Kaby | Coffee Z370 | Coffee Z390 | Comet 400 |
| --- | --- | --- | --- | --- | --- |
| SetupVirtualMap | YES | YES | YES often | **NO** most | **NO** |
| EnableWriteUnprotector | YES | YES | NO | NO | NO |
| RebuildAppleMemoryMap | NO | NO | YES | YES | YES |
| SyncRuntimePermissions | NO | NO | YES | YES | YES |
| DevirtualiseMmio | NO | NO | NO | **YES** | **YES** |
| ProtectUefiServices | NO | NO | NO | **YES** | **YES** |
| IgnoreInvalidFlexRatio | **YES** | NO | NO | NO | NO |
| AppleXcpmCfgLock | if CFG-Lock | if CFG-Lock | if CFG-Lock | if CFG-Lock | if CFG-Lock |

Gigabyte firmware often still wants SetupVirtualMap even when the generation table says no — kernel panic without it. ASUS Z490: do **not** enable SetupVirtualMap.

## SSDTs

See [ssdts.md](../common/ssdts.md). Coffee true-300 needs PMC. Comet Asus needs RHUB.

## iGPU

WhateverGreen + ig-platform-id. Haswell/Broadwell tables on the Haswell page. Skylake+ uses the values on each later page (not copied here — look up the live table; they change).

Ventura+ dropped Haswell–Skylake iMac SMBIOS. Either stay on Monterey or move SMBIOS to Kaby+ **and** use a supported dGPU if the iGPU is out of the OS.

## Ethernet

Intel GbE → IntelMausi. 2.5G Realtek on late 400/500 boards → LucyRTL8125Ethernet (`intel_alder_raptor` already recommends it; some Z490 too).
