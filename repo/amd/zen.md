# AMD Zen / Threadripper

Page: https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html  
Patches: https://github.com/AMD-OSX/AMD_Vanilla  
Studio: `amd_zen_legacy`, `amd_ryzen_zen3_4`. Patches live in `data/amd_patches.plist`.

## Non-negotiable

1. Kernel → DummyPowerManagement **YES**
2. Kernel → ProvideCurrentCpuInfo **YES** (OC 0.7.1+)
3. AMD Vanilla Kernel → Patch set, with **four** `algrey - Force cpuid_cores_per_package` Replace values set to **physical cores** as a hex byte
4. Lilu → VirtualSMC → WEG → AppleALC (no SMCProcessor on AMD)
5. SSDT-EC-USBX; **SSDT-CPUR only on B550/A520**
6. No CPUFriend, no IntelMausi (unless you added an Intel NIC)

Core count examples: 6=`06`, 8=`08`, 12=`0C`, 16=`10`, 24=`18`, 32=`20`. SMT does not change this — physical cores only.

## Booter

| Quirk | Default Zen | Change when |
| --- | --- | --- |
| RebuildAppleMemoryMap | YES | Early OEM fail → off + WriteUnprotector on |
| EnableWriteUnprotector | NO | see above |
| SyncRuntimePermissions | YES | — |
| SetupVirtualMap | YES | **NO** on X570/B550/A520/TRx40 and many late B450/X470 BIOS |
| DevirtualiseMmio | NO | **YES** on TRx40 + KASLR whitelist |
| ResizeAppleGpuBars | -1 | 0 if ReBAR enabled |

## Zen 4 / 500-series Monterey+

Vanilla ships an **IOPCIFamily** patch. Required for Ryzen 7000 and also unblocks many MSI A520/B550/X570 on Monterey+. Leave it enabled for `amd_ryzen_zen3_4`.

PAT patches: Sequoia has a **separate** PAT patch. Enable one PAT variant, not both.

## SMBIOS / GPU

iMacPro1,1 or MacPro7,1 with a supported dGPU. APU iGPU → [apu-nooted.md](apu-nooted.md).

Reddit r/hackintosh Sequoia Ryzen reports: mismatched SMBIOS caused sleep bugs; USB mapping took longer than kexts. Same as Dortania.

## FX / Jaguar (15h/16h)

Different Dortania page (`AMD/fx.md`). XLNCUSBFix, DummyPM, older patches. Studio `amd_zen_legacy` is Zen, not FX.
