# OpenCore Studio knowledge notes

Reference notes for hardware profiles and the in-app boot troubleshooter. Text only. Binaries stay at their upstream URLs — see [FILE-LOCATIONS.md](FILE-LOCATIONS.md).

This folder is not a replacement for the [Dortania OpenCore Install Guide](https://dortania.github.io/OpenCore-Install-Guide/). It maps which quirk, kext, SSDT, or driver belongs on which Intel or AMD generation, where the file is downloaded from, and which boot symptom it is tied to.

## How to use it

| You want… | Open |
| --- | --- |
| Where a kext / driver / SSDT is downloaded from | [FILE-LOCATIONS.md](FILE-LOCATIONS.md) |
| Symptom → cause → Studio action | [TROUBLESHOOTER.md](TROUBLESHOOTER.md) |
| Studio profile id vs Dortania page vs required files | [PROFILE-MATRIX.md](PROFILE-MATRIX.md) |
| Booter / Kernel / UEFI quirk notes | [common/quirks.md](common/quirks.md) |
| Intel desktop (Haswell → Comet) | [intel/desktop-haswell-comet.md](intel/desktop-haswell-comet.md) |
| Intel HEDT X99 / X299 / Xeon W | [intel/hedt-x99-x299.md](intel/hedt-x99-x299.md) |
| Alder / Raptor / Meteor / Rocket | [intel/hybrid-alder-meteor.md](intel/hybrid-alder-meteor.md) |
| Laptops (PNLF, GPIO, Ice Lake RHUB) | [intel/laptops.md](intel/laptops.md) |
| AMD Zen / Threadripper | [amd/zen.md](amd/zen.md) |
| AMD APU (NootedRed) | [amd/apu-nooted.md](amd/apu-nooted.md) |
| Dell Precision T5810 / T7910 | [machines/dell-t5810-t7910.md](machines/dell-t5810-t7910.md) |
| Source URLs | [SOURCES.md](SOURCES.md) |
| What Studio does not cover yet | [GAPS.md](GAPS.md) |

## Conventions

1. **Paraphrase and link.** Dortania, Acidanthera, and forum posts stay at their URLs. Do not paste Sample.plist or entire guide pages.
2. **Never enable a UEFI driver whose `.efi` is not in `EFI/OC/Drivers`.** OpenCore treats a missing enabled driver as a halt.
3. **Installer USB is not post-install.** USB maps, RestrictEvents extras, and OpenCanopy wait until the system already boots, unless the profile cannot start without them.
4. **Lilu first.** Then plugins. CpuTscSync is a Lilu plugin and must load after Lilu.
5. **Community EFI folders are hints, not profiles.** Copy quirks and file names, not someone else’s serials or USB map.

Studio profile JSON lives in `data/profiles/`. These notes are the *why*.
