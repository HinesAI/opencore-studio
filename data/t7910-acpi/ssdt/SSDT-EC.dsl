/*
 * T7910 fake Embedded Controller. Dump has no PNP0C09.
 * Parent from DSDT: _SB.PCI0.LPC0 (not LPCB).
 */
DefinitionBlock ("", "SSDT", 2, "OCS", "SsdtEC", 0x00001000)
{
    External (_SB_.PCI0.LPC0, DeviceObj)

    Scope (\_SB.PCI0.LPC0)
    {
        Device (EC)
        {
            Name (_HID, "ACID0001")
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Return (Zero)
            }
        }
    }
}
