# Known gaps

What a complete generator would still need, versus what Studio profiles and the troubleshooter cover today.

## Profiles

| Missing or thin | Notes |
| --- | --- |
| Intel laptop tree | Needs its own JSON plus PNLF / laptop EC tables |
| Broadwell desktop (non-E) | Shares the Haswell desktop page; no separate profile |
| Ivy / Sandy desktop | Legacy IgnoreInvalidFlexRatio and IMEI mixes |
| FX / Jaguar AMD | Separate from `amd_zen_legacy` |
| Rocket Lake iGPU spoof table | Treated as dGPU-only for now |
| Meteor / Arrow | Experimental |

## Troubleshooter symptoms still worth adding

From [TROUBLESHOOTER.md](TROUBLESHOOTER.md): `missing_uefi_driver`, `iopcifamily_x99`, `awac_rtc`, `amd_core_count`, `hybrid_topology`, `mce_reporter`.

## EFI builder

- Optional OcBinaryData `HfsPlus.efi` instead of OpenHfsPlus
- Per-chassis USB maps stay post-install

## Dell T5810 / T7910 still machine-specific

- AppleALC layout (T5810 notes often use 17)
- Whether a dual-socket MacPro7,1 setup needs AppleMCEReporterDisabler
- Whether `npci=0x2000` is required with Above 4G Decoding
- USB map for a given chassis
- Sleep / wake is often left off on Dell C612
