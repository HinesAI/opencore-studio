/*
 * T7910 USBX power properties (Skylake-style values used on X99/C612).
 * Fake EC lives in SSDT-EC.aml — this table does not create a second EC.
 */
DefinitionBlock ("", "SSDT", 2, "OCS", "UsbX", 0x00001000)
{
    Scope (\_SB)
    {
        Device (USBX)
        {
            Name (_ADR, Zero)
            Method (_DSM, 4, NotSerialized)
            {
                If ((Arg2 == Zero))
                {
                    Return (Buffer (One) { 0x03 })
                }
                Return (Package (0x08)
                {
                    "kUSBSleepPowerSupply", 0x13EC,
                    "kUSBSleepPortCurrentLimit", 0x0834,
                    "kUSBWakePowerSupply", 0x13EC,
                    "kUSBWakePortCurrentLimit", 0x0834
                })
            }
        }
    }
}
