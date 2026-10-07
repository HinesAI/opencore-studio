# USB

## Installer stick (Studio policy)

1. XhciPortLimit **false** on macOS 11.3+.
2. Do **not** ship USBToolBox + UTBMap (map is per board; a foreign map kills ports).
3. Do **not** ship USBInjectAll on the Sequoia installer.
4. BIOS: XHCI Hand-off on, EHCI Hand-off on if present.
5. UEFI → ReleaseUsbOwnership true if “Waiting for Root Device”.
6. Try USB 2.0 vs 3.x rear ports. Front-panel Dell T7910 is proprietary — use a rear port for the installer.

## After macOS is installed

Map on the **target** machine:

- USBToolBox (Windows or macOS) → `UTBMap.kext` + `USBToolBox.kext`
- or CorpNewt USBMap → `USBMap.kext`

Then keep XhciPortLimit false. Remove USBInjectAll if you used it only to map.

Intel Coffee Lake and older sometimes still need USBInjectAll **during mapping only**.

## SSDT-RHUB / USB Reset

Need a USB reset SSDT when ACPI presents a broken root hub:

- Asus Intel 400-series (Comet)
- Ice Lake laptops (often Dell)
- AMD (SSDTTime option 7)

Gigabyte / AsRock Intel 400 often do **not** need RHUB.

## XHCI-unsupported.kext

Dortania gathering-files: H370, B360, H310, Z390 (not Mojave+), **X79, X99**, many ASRock Intel. AMD does not need it. Goes in Kexts + Kernel → Add.

## 15-port limit

macOS counts USB2 and USB3 personalities. 15 is the cap per controller. Mapping is the fix, not XhciPortLimit, past 11.3.
