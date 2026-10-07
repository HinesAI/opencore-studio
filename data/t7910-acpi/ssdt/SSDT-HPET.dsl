/*
 * T7910 HPET IRQ fix. Dump path: _SB.PCI0.LPC0.HPET (Method _CRS).
 * Requires ACPI patches: HPET _CRS→XCRS, TMR IRQ 0, RTC IRQ 8
 * (those unique 5-byte finds match this DSDT once each).
 */
DefinitionBlock ("", "SSDT", 2, "OCS", "HPET", 0x00000000)
{
    External (_SB_.PCI0.LPC0.HPET, DeviceObj)
    External (_SB_.PCI0.LPC0.HPET.XCRS, MethodObj)

    Scope (\_SB.PCI0.LPC0.HPET)
    {
        Name (BUFX, ResourceTemplate ()
        {
            IRQNoFlags () { 0, 8 }
            Memory32Fixed (ReadWrite, 0xFED00000, 0x00000400)
        })
        Method (_CRS, 0, Serialized)
        {
            If (_OSI ("Darwin"))
            {
                Return (BUFX)
            }
            Return (XCRS ())
        }
    }
}
