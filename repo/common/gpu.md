# GPU

Buyers guide: https://dortania.github.io/GPU-Buyers-Guide/

## Sequoia-era reality

- **Works:** AMD Polaris, Vega, Navi 10/20 (RX 5000/6000 except Navi 22), Intel iGPU through Comet/Ice (generation-dependent), some Rocket spoofs
- **Needs extra kext:** Navi 22 (6700/6750) → NootRX; Ryzen APU iGPU → NootedRed
- **Dead:** NVIDIA as of Monterey (Kepler included)

No iGPU on Haswell-E / Broadwell-E / Xeon E5 v3/v4 / many W-series. T7910 **requires a discrete UEFI AMD GPU**.

## Navi black screen

`agdpmod=pikera`. CSM off. GOP. Try DP then HDMI. WhateverGreen loaded after Lilu.

## iGPU DeviceProperties

Dortania tables (hex as shown on the page — convert to DATA bytes reversed):

- Haswell display `0300220D`, compute `04001204`
- Broadwell display `07002216`

Headless: compute id + dGPU as primary in BIOS.

## SMBIOS vs GPU

iGPU-only iMac SMBIOS with no working iGPU = black screen or no acceleration. HEDT/AMD dGPU → iMacPro1,1 or MacPro7,1.

## WhateverGreen vs Nooted*

Never mix. Studio profiles already split `amd_apu_nooted` vs dGPU WhateverGreen profiles.
