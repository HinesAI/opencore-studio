# Intel laptops (and AIO)

Dortania has a full laptop tree (Clarksfield → Ice Lake) under the config.plist picker. Studio does not yet ship laptop profiles; this page is so the troubleshooter can still name the files.

## Extra vs desktop

| Item | Laptop |
| --- | --- |
| SSDT-PNLF | Backlight |
| SSDT-EC-USBX-**LAPTOP** | Do not disable the real EC |
| SSDT-GPI0 / VoodooI2C | I2C trackpads (order: VoodooGPIO, VoodooI2CServices, VoodooInput, then VoodooI2C, then satellite) |
| VoodooPS2 | PS/2 keyboards |
| SMCBatteryManager | Battery |
| BrightnessKeys | ACPI brightness keys |
| ECEnabler | Multi-byte EC (0% battery) |
| XOSI | Hacky Windows OSI; GPIO SSDT preferred |
| IRQ patches | Broadwell and older; SSDTTime |

Ice Lake laptops: SSDT-RHUB (Dell especially), “Wrong CD Clock Frequency” WEG flags, DevirtualiseMmio + ProtectUefiServices.

Scrambled internal LCD: usually framebuffer / PNLF / `-igfxcdlr` type WEG flags — use the live laptop page for that generation.

Battery: never rename EC on laptops the desktop way.
