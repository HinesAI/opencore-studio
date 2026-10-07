# Sources

Primary docs first. Forums and GitHub EFIs are second-class: they confirm machine-specific bugs Dortania does not list.

## Dortania (canonical for profiles)

| Topic | URL |
| --- | --- |
| Install guide index | https://dortania.github.io/OpenCore-Install-Guide/ |
| config.plist platform picker | https://dortania.github.io/OpenCore-Install-Guide/config.plist/ |
| Gathering files (kexts / drivers) | https://dortania.github.io/OpenCore-Install-Guide/ktext.html |
| Kernel issues (EXITBS, root device, IOPCIFamily, Navi black, MCE) | https://dortania.github.io/OpenCore-Install-Guide/troubleshooting/extended/kernel-issues.html |
| USB mapping (post-install) | https://dortania.github.io/OpenCore-Post-Install/usb/ |
| Intel USB map | https://dortania.github.io/OpenCore-Post-Install/usb/intel-mapping/intel.html |
| OpenCanopy / AudioDxe | https://dortania.github.io/OpenCore-Post-Install/cosmetic/gui.html |
| GPU buyers | https://dortania.github.io/GPU-Buyers-Guide/ |
| ACPI / SSDTs | https://dortania.github.io/Getting-Started-With-ACPI/ |
| Prebuilt SSDT list | https://dortania.github.io/Getting-Started-With-ACPI/ssdt-methods/ssdt-prebuilt.html |
| Compiled AML | https://github.com/dortania/Getting-Started-With-ACPI/tree/master/extra-files/compiled |
| HEDT RTC range | https://dortania.github.io/Getting-Started-With-ACPI/Universal/awac-methods/manual-hedt.html |

### Intel desktop config pages

- Haswell / Broadwell: https://dortania.github.io/OpenCore-Install-Guide/config.plist/haswell.html
- Skylake: https://dortania.github.io/OpenCore-Install-Guide/config.plist/skylake.html
- Kaby Lake: https://dortania.github.io/OpenCore-Install-Guide/config.plist/kaby-lake.html
- Coffee Lake: https://dortania.github.io/OpenCore-Install-Guide/config.plist/coffee-lake.html
- Comet Lake: https://dortania.github.io/OpenCore-Install-Guide/config.plist/comet-lake.html

### Intel HEDT

- Haswell-E: https://dortania.github.io/OpenCore-Install-Guide/config-HEDT/haswell-e.html
- Broadwell-E: https://dortania.github.io/OpenCore-Install-Guide/config-HEDT/broadwell-e.html
- Skylake-X / Cascade-X/W: https://dortania.github.io/OpenCore-Install-Guide/config-HEDT/skylake-x.html

### AMD

- Zen / Threadripper 17h/19h: https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html
- AMD Vanilla patches: https://github.com/AMD-OSX/AMD_Vanilla

## Acidanthera

| Project | URL |
| --- | --- |
| OpenCorePkg releases (EFI tree, Sample.plist, Tools, most Drivers) | https://github.com/acidanthera/OpenCorePkg/releases |
| OcBinaryData (HfsPlus.efi, Resources, extra FS drivers) | https://github.com/acidanthera/OcBinaryData |
| Kexts.md (min/max kernel) | https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Kexts.md |
| Lilu / VirtualSMC / WhateverGreen / AppleALC / IntelMausi / NVMeFix / RestrictEvents / CpuTscSync | each under https://github.com/acidanthera/ |

## Other upstreams used in Studio or this repo

| File / topic | URL |
| --- | --- |
| CpuTopologyRebuild (Alder/Raptor P+E) | https://github.com/b00t0x/CpuTopologyRebuild |
| NootedRed (AMD APU iGPU) | https://github.com/ChefKissInc/NootedRed |
| NootRX (Navi 22 dGPU) | https://github.com/ChefKissInc/NootRX |
| USBToolBox kext + mapper | https://github.com/USBToolBox/kext and https://github.com/USBToolBox/tool |
| USBInjectAll | https://github.com/Sniki/OS-X-USB-Inject-All (Dortania still cites this for Coffee Lake and older mapping) |
| XHCI-unsupported | https://github.com/RehabMan/OS-X-USB-Inject-All related / Dortania gathering-files list |
| TSCAdjustReset.kext (X299 style) | https://github.com/interferenc/TSCAdjustReset |
| CpuTscSync.kext (current Monterey+ TSC_ADJUST reset) | https://github.com/acidanthera/CpuTscSync |
| AppleMCEReporterDisabler | community; Dortania kernel-issues page |
| LucyRTL8125Ethernet | https://github.com/Mieze/LucyRTL8125Ethernet |
| RealtekRTL8111 | https://github.com/Mieze/RealtekRTL8111-Binary |
| itlwm / AirportItlwm | https://github.com/OpenIntelWireless/itlwm |
| IntelBluetoothFirmware | https://github.com/OpenIntelWireless/IntelBluetoothFirmware |

## Machine-specific (Dell T5810 / T7910)

| Source | What it is good for |
| --- | --- |
| https://github.com/BillDH2k/Hackintosh-DELL-T5810-OpenCore | Sequoia-era T5810 EFI notes: ResetTSCAdjust.efi as a *Driver*, USB map, alcid 17, MacPro7,1 / iMacPro1,1, BIOS A32–A34, sleep often disabled |
| https://github.com/Klubuntu/EFI-Dell-T5810 | Later Sequoia/Tahoe T5810; still ships ResetTSCAdjust.efi |
| https://github.com/denskop/VoodooTSCSync/issues/1#issuecomment-629837192 | denskop ResetTSCAdjust.efi origin (not in OpenCore 1.0.x RELEASE zip) |
| https://www.insanelymac.com/forum/topic/354610-trying-to-install-macos-ventura-on-dell-precision-t5810/ | Non-monotonic time identified as Dell C612 TSC, not EXITBS |
| https://www.insanelymac.com/forum/topic/351465-need-help-installing-monterey-on-dell-precision-tower-7910/ | T7910 Monterey: `cpus=1` workaround; CpuTscSync / VoodooTSCSync |
| https://www.insanelymac.com/forum/topic/358685-dell-precision-t7910-x99-c612-hardware-issues-on-sonoma-ventura/ | T7910 Sonoma: 64-thread cap, extra PCI SSDTs, UNC/USBX cleanup |

## Forums / Reddit (spot-check, not gospel)

- r/hackintosh — Ryzen Sequoia: Dortania + iMacPro1,1 + USB map; no configurators
- InsanelyMac OpenCore general discussion — UEFI Drivers LoadEarly, OpenVariableRuntimeDxe
- tonymacx86 X299 threads — TSCAdjustReset.kext on Skylake-X (kext, not efi)

Quirk comparison tables also appear on DeepWiki mirrors of Dortania (`deepwiki.com/dortania/OpenCore-Install-Guide`). Prefer the live Dortania HTML when they disagree.
