# Intel HEDT — X99, X299, Xeon W

Pages:

- https://dortania.github.io/OpenCore-Install-Guide/config-HEDT/haswell-e.html
- https://dortania.github.io/OpenCore-Install-Guide/config-HEDT/broadwell-e.html
- https://dortania.github.io/OpenCore-Install-Guide/config-HEDT/skylake-x.html

Studio: `intel_haswell_e`, `intel_broadwell_e`, `intel_skylake_x`, `intel_xeon_w_skylake`, `intel_xeon_w_cascade`.

No consumer iGPU. Discrete AMD GPU + iMacPro1,1 (or MacPro7,1).

## Haswell-E vs Broadwell-E (X99 / C612)

Same SSDTs and almost the same quirks. **CPUID spoof differs.**

| | Haswell-E | Broadwell-E |
| --- | --- | --- |
| SKUs | i7-58xx/59xxX, E5 v3 | i7-68xx/69xxX, E5 v4 |
| Cpuid1Data | `C3060300 00000000 00000000 00000000` | `D4060300 00000000 00000000 00000000` |
| Cpuid1Mask | `FFFFFFFF 00000000 00000000 00000000` | same |
| SSDTs | PLUG, EC-USBX, RTC0-RANGE-HEDT, UNC | same |
| AppleXcpmExtraMsrs | YES | YES |
| IgnoreInvalidFlexRatio | YES | YES |
| LegacyOverwrite | YES | YES |
| WriteFlash | NO | NO |
| SetupVirtualMap | YES | YES |
| DevirtualiseMmio | **NO** | **NO** |
| npci=0x2000 | common if Above 4G broken | same |

IOPCIFamily panic → UNC missing or DevirtualiseMmio on.

Big Sur+ halt in RTC → RTC0-RANGE-HEDT missing or wrong ACPI path.

## Skylake-X / Cascade-X / Xeon W (X299 / C422)

- No CPUID spoof
- SSDTs: PLUG, EC-USBX, RTC0-RANGE-HEDT (**no UNC** on Dortania)
- RebuildAppleMemoryMap YES, DevirtualiseMmio YES, SyncRuntimePermissions YES
- EnableWriteUnprotector NO
- SetupVirtualMap YES except **ASUS BIOS v3006+**
- AppleXcpmExtraMsrs **NO** on the Skylake-X page (DeepWiki tables sometimes say YES — prefer the live Dortania HTML)
- WriteFlash YES
- TSC: TSCAdjustReset.kext is the old X299 trick; CpuTscSync is the maintained Lilu plugin

2020+ X299 BIOS: SetupVirtualMap may cause EXITBS (same bucket as Comet/B550).

## Dual socket

macOS topology gets ugly past 64 threads (T7910 Sonoma thread). MCE reporter panics on MacPro7,1 → AppleMCEReporterDisabler.

## USB on X99

XHCI-unsupported.kext + later a chassis-specific map. Dell front panel is not a standard header — map rear ports first.

Dell Precision C612 BIOS also desyncs TSC — [dell-t5810-t7910.md](../machines/dell-t5810-t7910.md).
