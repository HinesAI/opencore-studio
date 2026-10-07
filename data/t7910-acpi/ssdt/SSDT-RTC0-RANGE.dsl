/*
 * T7910 RTC range. OEM RTC _CRS is 0x70-0x71 + 0x74-0x77 (hole at 0x72-0x73).
 * Hide OEM RTC on Darwin and expose an 8-byte 0x70-0x77 RTC0 for AppleRTC.
 */
DefinitionBlock ("", "SSDT", 2, "OCS", "RtcRange", 0x00000000)
{
    External (_SB_.PCI0.LPC0, DeviceObj)
    External (_SB_.PCI0.LPC0.RTC_, DeviceObj)

    Scope (\_SB.PCI0.LPC0.RTC)
    {
        Method (_STA, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Return (Zero)
            }
            Return (0x0F)
        }
    }

    Scope (\_SB.PCI0.LPC0)
    {
        Device (RTC0)
        {
            Name (_HID, EisaId ("PNP0B00"))
            Name (_CRS, ResourceTemplate ()
            {
                IO (Decode16, 0x0070, 0x0070, 0x01, 0x08)
            })
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
