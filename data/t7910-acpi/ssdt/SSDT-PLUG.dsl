/*
 * T7910 dual-socket XCPM plugin-type.
 * Dump path: _SB.SCK0.CP00 (socket 0) and _SB.SCK1.CP00 (socket 1).
 * Do not inject the OEM DSDT or SSDT-0-PmMgt.
 */
DefinitionBlock ("", "SSDT", 2, "OCS", "CpuPlug", 0x00003000)
{
    External (_SB_.SCK0.CP00, ProcessorObj)
    External (_SB_.SCK1.CP00, ProcessorObj)

    Method (PMPM, 4, NotSerialized)
    {
        If ((Arg2 == Zero))
        {
            Return (Buffer (One) { 0x03 })
        }
        Return (Package (0x02) { "plugin-type", One })
    }

    If (CondRefOf (\_SB.SCK0.CP00))
    {
        If ((ObjectType (\_SB.SCK0.CP00) == 0x0C))
        {
            Scope (\_SB.SCK0.CP00)
            {
                Method (_DSM, 4, NotSerialized)
                {
                    Return (PMPM (Arg0, Arg1, Arg2, Arg3))
                }
            }
        }
    }

    If (CondRefOf (\_SB.SCK1.CP00))
    {
        If ((ObjectType (\_SB.SCK1.CP00) == 0x0C))
        {
            Scope (\_SB.SCK1.CP00)
            {
                Method (_DSM, 4, NotSerialized)
                {
                    Return (PMPM (Arg0, Arg1, Arg2, Arg3))
                }
            }
        }
    }
}
