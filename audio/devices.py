from __future__ import annotations

import sounddevice as sd


def list_input_devices() -> list[tuple[int, str]]:
    devices: list[tuple[int, str]] = []
    for index, info in enumerate(sd.query_devices()):
        if int(info.get("max_input_channels", 0)) > 0:
            devices.append((index, str(info.get("name", f"Устройство {index}"))))
    return devices
