/*
 * T7910 SMBus / MCHC. Dump has _SB.PCI0.SMBS at 1F.3 and no MCHC.
 */
DefinitionBlock ("", "SSDT", 2, "OCS", "SBusMCHC", 0x00000000)
{
    External (_SB_.PCI0, DeviceObj)
    External (_SB_.PCI0.SMBS, DeviceObj)

    Scope (\_SB.PCI0)
    {
        Device (MCHC)
        {
            Name (_ADR, Zero)
        }
    }

    Scope (\_SB.PCI0.SMBS)
    {
        Device (BUS0)
        {
            Name (_CID, "smbus")
            Name (_ADR, Zero)
            Device (DVL0)
            {
                Name (_ADR, 0x57)
                Name (_CID, "diagsvault")
                Method (_DSM, 4, NotSerialized)
                {
                    If (!Arg2)
                    {
                        Return (Buffer (One) { 0x57 })
                    }
                    Return (Package (0x02) { "address", 0x57 })
                }
            }
        }
    }
}
