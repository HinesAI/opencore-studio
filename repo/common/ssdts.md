# SSDTs

Place `.aml` in `EFI/OC/ACPI` **and** ACPI → Add Enabled. Do not add dumped `DSDT.aml`.

Prebuilts: [FILE-LOCATIONS.md](../FILE-LOCATIONS.md). Full picker: https://dortania.github.io/Getting-Started-With-ACPI/ssdt-methods/ssdt-prebuilt.html

## By job

| SSDT | Job | Who |
| --- | --- | --- |
| PLUG / PLUG-DRTNIA | XCPM plugin-type on first CPU thread | Intel Haswell+ |
| PLUG-ALT | Hybrid / odd CPU order (Arrow / some Alder) | Experimental 12th+ |
| EC / EC-DESKTOP | Hide OEM EC, fake `EC` | Pre-Skylake desktop, HEDT Nehalem |
| EC-USBX-DESKTOP | Fake EC + USBX power | Skylake+ desktop, X99, X299, AMD |
| EC-USBX-LAPTOP | Fake EC without killing real EC | Laptops (battery) |
| AWAC | Force legacy RTC | 300-series (Z370 sometimes too) |
| RTC0 | Fake RTC when no legacy clock | When AWAC SSDT is wrong |
| RTC0-RANGE-HEDT | Fill RTC _CRS holes | **X99 / X299 Big Sur+** |
| PMC | MMIO NVRAM | True 300-series **not Z370** |
| RHUB | Reset USB root hub | Asus 400, Ice Lake, AMD |
| IMEI | Create IMEI | Sandy+7-series or Ivy+6-series mix |
| UNC | Disable dead uncore PCI | **X99 Big Sur+ IOPCIFamily** |
| CPUR | CPU ACPI objects | **AMD B550/A520 only** |
| PNLF | Backlight | Laptop / AIO |
| GPI0 / GPIO | I2C trackpad stub | Laptop |
| SBUS-MCHC | SMBus / MCHC | Post-install, T5810 GitHub EFIs include it |
| USBX (standalone) | USB power properties | If EC-USBX split |

## Intel desktop quick list

- Haswell/Broadwell desktop: PLUG, EC
- Skylake/Kaby: PLUG, EC-USBX
- Coffee: PLUG, EC-USBX, AWAC, PMC (if true 300)
- Comet: PLUG, EC-USBX, AWAC, RHUB if Asus

## Intel HEDT

- Sandy/Ivy-E: EC, UNC
- Haswell-E / Broadwell-E: PLUG, EC-USBX, RTC0-RANGE-HEDT, UNC
- Skylake-X / Cascade-X/W: PLUG, EC-USBX, RTC0-RANGE-HEDT (no UNC on Dortania list)

If prebuilt RTC0-RANGE does not match ACPI paths (`PC00.LPC0.RTC_` vs `PCI0.LPCB.RTC`), decompile DSDT, find `PNP0B00`, retarget the DSL, compile.

## AMD

- All Zen: EC-USBX
- B550 / A520: + CPUR
- X570 and older: no CPUR
- USB: SSDTTime USB Reset → RHUB when ports missing

## Studio aliases

`engine/efi_builder.py` downloads `SSDT-RTC0-RANGE-HEDT.aml` but writes `SSDT-RTC0-RANGE.aml` into the EFI because the profile Path is the short name. Same for PLUG-DRTNIA → PLUG and EC-USBX-DESKTOP → EC-USBX. The **file on disk must match Path**.
