# SMBIOS / PlatformInfo

Use CorpNewt GenSMBIOS or Studio’s generator. **Never copy serials from a GitHub EFI.**

PlatformInfo → Generic → Automatic true. Fill:

- SystemProductName (model)
- SystemSerialNumber
- MLB
- SystemUUID
- ROM (MAC-sized 6 bytes)

## Picking a model

See [PROFILE-MATRIX.md](../PROFILE-MATRIX.md). Match:

1. GPU situation (iGPU vs dGPU-only)
2. macOS version (Ventura dropped Haswell–Skylake iMacs)
3. CPU power management (iMacPro1,1 is the HEDT/AMD workhorse)

MacPro7,1: extra RAM DIMM warning → RestrictEvents. Dual CPU MCE panic → AppleMCEReporterDisabler.

## Apple services

Valid unused serials still get you nowhere without a real ROM and clean MLB pairing. Studio generates “Apple-like” values; the user owns iMessage/iCloud outcome.

## SecureBootModel

Disabled for install. After install, can set to the SMBIOS default (j174 etc.) if you want Apple Secure Boot; then Preboot must have matching manifests. When in doubt leave Disabled on a hack.
