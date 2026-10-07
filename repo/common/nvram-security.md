# NVRAM and security bits

## Native vs emulated NVRAM

Most 2013+ UEFI desktops have working NVRAM. True 300-series (not Z370) often need **SSDT-PMC**. If NVRAM still does not persist:

- OpenVariableRuntimeDxe.efi LoadEarly true, then OpenRuntime
- LegacySchema populated
- ResetNvramEntry then deletes `nvram.plist` instead of firmware NVRAM

Haswell-E Dortania: LegacyOverwrite YES, WriteFlash NO. Skylake-X: WriteFlash YES.

## Reset NVRAM

Driver: `ResetNvramEntry.efi`. Arguments `--preserve-boot` keeps BootOrder (Windows). HideAuxiliary false **or** Spacebar to show the entry. After reset, firmware boot order often puts Windows first — pick OC again.

Dell T7910: do this once after a bad EFI so leftover boot-args/csr are gone, then boot the installer.

## SIP / csr-active-config

`00000000` SIP on. Partial disable only when a kext (Broadcom, OCLP) documents it. OCLP is a different product; do not bake OCLP SIP bits into Studio profiles.

## Vault / FileVault

Vault Optional. FileVault on a hack needs AudioDxe + protocol overrides if you want VoiceOver; most users skip FileVault until post-install is boringly stable.
