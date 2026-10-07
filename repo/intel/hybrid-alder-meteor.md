# Intel hybrid — Rocket, Alder, Raptor, Meteor, Arrow

Dortania’s official desktop picker stops at Comet Lake. Everything here is Acidanthera + kext authors + forums. Treat as unstable relative to Haswell–Comet.

Studio: `intel_rocket_lake`, `intel_alder_raptor`, `intel_meteor_lake`.

## Rocket Lake (11th, 11xxx)

Often installed as **Comet Lake** with a dGPU (iMac20,1) because the iGPU is not a Comet UHD 630. Community iGPU spoofs exist; dGPU is the boring path. Quirks follow Comet (no SetupVirtualMap, DevirtualiseMmio + ProtectUefiServices). CFG-Lock / VT-d same.

## Alder / Raptor (12/13/14th)

Must:

- Kernel → ProvideCurrentCpuInfo **YES** (enables P+E, but all threads look equal)
- **CpuTopologyRebuild.kext** (b00t0x) after Lilu to rebuild P/E topology
- RestrictEvents for CPU name / VMM as needed
- SSDT-PLUG or PLUG-ALT if plugin-type path is wrong
- 2.5G Realtek → LucyRTL8125Ethernet on many B660/Z690/Z790

BIOS: often need to disable Resizable BAR or set ResizeAppleGpuBars 0. CFG-Lock, VT-d, Above 4G, XHCI Hand-off still apply. Some boards need “enable Intel VT for Directed I/O” off.

E-cores: can boot with them on if topology kext + ProvideCurrentCpuInfo are correct. If not, disable E-cores in BIOS to prove the box, then add the kext.

## Meteor / Arrow (Core Ultra)

Experimental. CpuTopologyRebuild lists Arrow as experimental. Some Arrow SKUs (225F) still fail with odd APIC order even with PLUG-ALT. Be ready to disable E-cores. Do not promise Sequoia in Studio copy until a machine is in-house.

## iGPU

12th+ Intel iGPU in macOS is not Dortania-blessed. Many builds are **dGPU only** (WhateverGreen + iMacPro1,1 / iMac20,x). NootedRed is AMD APU, not Intel.
