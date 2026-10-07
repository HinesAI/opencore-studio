# Boot-args

Space-separated NVRAM `7C436110-AB2A-4BBB-A880-FE41995C9F82` → `boot-args`.

## Always useful while installing

| Arg | Why |
| --- | --- |
| `-v` | Verbose |
| `keepsyms=1` | Symbols in panic |
| `debug=0x100` | Debug output |

Remove `-v` after the machine is stable if you want the Apple logo.

## Audio

| Arg | Why |
| --- | --- |
| `alcid=1` | Default layout; **wrong on many boards** |
| `alcid=11` / `13` / `17` / … | Try from AppleALC supported codecs. T5810 reports **17** (ALC280) — confirm T7910 codec in IOReg |

## GPU (WhateverGreen)

| Arg | Use on | Do not use on |
| --- | --- | --- |
| `agdpmod=pikera` | RX 5000 / 6000 Navi black screen | Polar / Vega |
| `-radcodec` | Spoofed AMD encoder | — |
| `radpg=15` | Cape Verde | Newer AMD |
| `unfairgva=1` | AMD DRM | — |
| `-igfxvesa` | Prove Intel iGPU is framebuffer | Daily |
| `-wegnoegpu` | Force iGPU, disable dGPU | Dual GPU debug |
| `nvda_drv_vrl=1` | Maxwell/Pascal Web Drivers | **High Sierra only** |

## CPU / TSC / topology

| Arg | Why |
| --- | --- |
| `cpus=1` | Prove TSC/xcall panics (Dell T7910 Monterey thread) |
| `ctrsmt=off` / `ctrsmt=full` | CpuTopologyRebuild modes |
| `-ctrfixcnt` | CpuTopologyRebuild core_count fix; needs AppleMCEReporterDisabler |
| `revcpu=1` / RestrictEvents args | CPU name string; see RestrictEvents README |

## USB / PCI

| Arg | Why |
| --- | --- |
| `npci=0x2000` | PCI config above 4G; **common on X99** if Above 4G is off or broken |
| `npci=0x3000` | Alternate |
| `amfi_get_out_of_my_way=1` | Breaks AMFI; last resort, not for daily |

Prefer enabling **Above 4G Decoding** in BIOS over living on `npci=`.

## Debug extras

`msgbuf=1048576`, `-liludbgall`, `liludump=60` — Lilu/WEG debug. Huge logs. Off for USB sticks you will actually install from.
