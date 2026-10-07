# Known boards (forum / GitHub pointers)

Not a support list. Jumping-off points when a Studio profile is “right generation, wrong OEM.”

| Board / OEM | Generation | Notes / search seeds |
| --- | --- | --- |
| Dell T5810 / T7810 / T7910 | X99 C612 | [dell-t5810-t7910.md](dell-t5810-t7910.md) |
| HP Z440 / Z640 / Z840 | X99 | Similar TSC/X99 SSDTs; some people fled T5810 to Z440 |
| ASUS X299 SAGE / WS | Skylake-X | TSCAdjustReset.kext; Above 4G for USB; ASUS v3006+ SetupVirtualMap off |
| Gigabyte Z390 | Coffee | SetupVirtualMap often still YES; DevirtualiseMmio + ProtectUefiServices |
| ASUS Z490 / B460 | Comet | SSDT-RHUB; SetupVirtualMap NO |
| MSI B550 / X570 | Zen 3 | SetupVirtualMap NO; IOPCIFamily patch; SSDT-CPUR on B550 |
| Gigabyte B550 | Zen 3 | CPUR; USB map; 2.5G Realtek |
| ASRock B660 / Z690 | Alder | ProvideCurrentCpuInfo + CpuTopologyRebuild; LucyRTL8125 |
| Dell Ice Lake laptops | Ice Lake | SSDT-RHUB, CD clock WEG flags |
| Proxmox / QEMU | VM | SetupVirtualMap NO; virtio vs emulated GPU |

When adding a new Studio machine page: link Dortania generation first, then only OEM deltas (TSC, USB header, NIC, audio layout, BIOS names).
