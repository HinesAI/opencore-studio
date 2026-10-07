# Kexts (load order and conflicts)

Kernel → Add order is load order. Studio `priority` in `data/kexts.json` encodes this.

## Required stack

1. **Lilu**
2. **CpuTscSync** (only HEDT/Dell/X299 TSC machines) — Lilu plugin, keep it early
3. **VirtualSMC**
4. SMC* plugins
5. **WhateverGreen** *or* NootedRed *or* NootRX (one graphics family)
6. **AppleALC**
7. Ethernet / Wi-Fi / BT
8. NVMeFix, RestrictEvents, CpuTopologyRebuild
9. USB map kexts last

## Conflicts

| Do not combine | Why |
| --- | --- |
| VirtualSMC + FakeSMC | Double SMC |
| WhateverGreen + NootedRed | APU vs dGPU patchers |
| WhateverGreen + NootRX | Navi 22 |
| USBInjectAll + final USBMap | Apple’s merger fights USBInjectAll |
| USBToolBox without UTBMap | Useless / can confuse |
| Two AirportItlwm builds | One macOS version zip |
| AMD Vanilla DummyPM off | Won’t boot |
| CpuFriend + AMD DummyPM | AMD uses DummyPM, not CPUFriend |

## Ethernet pick

| Chip | Kext |
| --- | --- |
| Intel I217/I219/I211-ish onboard (Dell T7910) | IntelMausi |
| Intel I225 / I226 | IntelLucy / SmallTree / AppleIGC (check current Acidanthera) |
| RTL8111/8168 | RealtekRTL8111 |
| RTL8125 2.5G | LucyRTL8125Ethernet |
| Killer E2200 | AtherosE2200Ethernet |

Wrong ethernet kext does not usually panic; it just leaves you without LAN in the installer (bad for recovery).

## Wi-Fi / BT

Broadcom Fenvi native > Intel itlwm > USB dongles.

Monterey+: Broadcom needs BlueToolFixup; Intel needs IntelBluetoothFirmware + IntelBTPatcher + BlueToolFixup as documented in OpenIntelWireless.

## Graphics kexts

- Discrete AMD / Intel iGPU: WhateverGreen
- Ryzen APU iGPU: NootedRed, remove WEG
- RX 6700 XT class: NootRX, remove WEG
- NVIDIA: High Sierra Web Drivers only for Maxwell/Pascal; Kepler died in Monterey

## HEDT extras

- CpuTscSync — Dell C612 Sequoia (Studio)
- TSCAdjustReset — older X299
- XHCI-unsupported — X99 USB3
- AppleMCEReporterDisabler — MacPro7,1 dual socket
- RestrictEvents — MacPro7,1 DIMM popup (`revpatch` as needed)
