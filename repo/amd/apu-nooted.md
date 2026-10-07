# AMD APU (NootedRed)

Studio: `amd_apu_nooted`.

Ryzen 3000–6000 **APU iGPU** (Vega / Navi2 iGPU), no dGPU or dGPU disabled.

- Kext: **NootedRed** (ChefKissInc/NootedRed), Lilu first
- **Remove WhateverGreen**
- Still need AMD Vanilla + DummyPM + ProvideCurrentCpuInfo + EC-USBX ± CPUR
- SMBIOS: typically MacBookPro / iMac with iGPU, but many still use iMacPro1,1 — follow current NootedRed README (it changes)
- HDMI/DP audio: AppleALC + layout; may need NootedRed properties

NootRX is a **different** kext for RX 6700 **desktop** dGPUs, also incompatible with WEG.
