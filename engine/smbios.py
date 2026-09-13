"""OpenCore Studio — PlatformInfo / SMBIOS Generator.

Implements authentic Apple serial number generation, Board Serial Number (MLB),
SystemUUID, and ROM generation based on GenSMBIOS logic.
"""

from __future__ import annotations

import random
import string
import uuid
from typing import Any

# Common Model Codes (last 4 characters of 12-char serial)
MODEL_CODES: dict[str, dict[str, Any]] = {
    "iMac20,1": {"code": "PN5T", "mlb_prefix": "C02", "model": "iMac (Retina 5K, 27-inch, 2020)"},
    "iMac20,2": {"code": "042H", "mlb_prefix": "C02", "model": "iMac (Retina 5K, 27-inch, 2020 Core i9)"},
    "iMac19,1": {"code": "JV3Q", "mlb_prefix": "C02", "model": "iMac (Retina 5K, 27-inch, 2019)"},
    "iMac18,1": {"code": "H7JY", "mlb_prefix": "C02", "model": "iMac (21.5-inch, 2017)"},
    "iMac18,3": {"code": "J1GJ", "mlb_prefix": "C02", "model": "iMac (Retina 5K, 27-inch, 2017)"},
    "iMacPro1,1": {"code": "HX87", "mlb_prefix": "C02", "model": "iMac Pro (2017)"},
    "MacPro7,1": {"code": "P7QM", "mlb_prefix": "F5K", "model": "Mac Pro (2019)"},
    "Macmini8,1": {"code": "JYVY", "mlb_prefix": "C07", "model": "Mac mini (2018)"},
    "MacBookPro16,1": {"code": "MD6T", "mlb_prefix": "C02", "model": "MacBook Pro (16-inch, 2019)"},
    "MacBookPro15,1": {"code": "KGYG", "mlb_prefix": "C02", "model": "MacBook Pro (15-inch, 2018)"},
}

ALPHANUM = string.ascii_uppercase + string.digits


def _random_chars(length: int) -> str:
    return "".join(random.choices(ALPHANUM, k=length))


def generate_smbios(model: str = "iMac20,1") -> dict[str, Any]:
    """Generates an authentic set of matching serials for an Apple SMBIOS model."""
    meta = MODEL_CODES.get(model, {"code": "PN5T", "mlb_prefix": "C02", "model": model})
    prefix = meta["mlb_prefix"]
    model_code = meta["code"]

    # 12-character Serial Number:
    # 3-char location code + 2-char year/week code + 3-char unique ID + 4-char model code
    loc = random.choice(["C02", "D25", "F5K", "W80", "C07"])
    year_week = random.choice(["D" + str(random.randint(1, 9)), "F" + str(random.randint(1, 9)), "G" + str(random.randint(1, 9))])
    unique = _random_chars(3)
    serial = f"{loc}{year_week}{unique}{model_code}"

    # 17-character Board Serial Number (MLB):
    # Prefix (3) + Year/Week/Plant (5) + Sequence (5) + Suffix/Model code (4)
    mlb = f"{loc}{_random_chars(5)}{_random_chars(5)}{_random_chars(4)}"

    # System UUID (Version 4 UUID)
    system_uuid = str(uuid.uuid4()).upper()

    # ROM: 6 hex bytes (MAC Address format without colons, e.g. 112233445566)
    rom_bytes = bytes([random.randint(0, 255) for _ in range(6)])
    rom_hex = rom_bytes.hex().upper()

    return {
        "model": model,
        "serial": serial,
        "mlb": mlb,
        "uuid": system_uuid,
        "rom": rom_hex,
        "SystemProductName": model,
        "SystemSerialNumber": serial,
        "MLB": mlb,
        "SystemUUID": system_uuid,
        "ROM": rom_bytes,
        "ROMHex": rom_hex,
        "ModelDescription": meta["model"],
        "Generic": {
            "AdviseFeatures": False,
            "MaxBIOSVersion": False,
            "ProcessorType": 0,
            "SystemMemoryStatus": "Auto",
            "SystemProductName": model,
            "SystemSerialNumber": serial,
            "SystemUUID": system_uuid,
            "MLB": mlb,
            "ROM": rom_bytes,
            "SpoofVendor": True
        },
        "PlatformInfo": {
            "Automatic": True,
            "CustomMemory": False,
            "UpdateDataHub": True,
            "UpdateNVRAM": True,
            "UpdateSMBIOS": True,
            "UpdateSMBIOSMode": "Create"
        }
    }


def list_models() -> list[dict[str, str]]:
    """Lists all pre-configured SMBIOS models with description."""
    return [
        {"id": k, "name": k, "description": v["model"]}
        for k, v in MODEL_CODES.items()
    ]
