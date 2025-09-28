"""
CI sitecustomize.py - Configures default audio device for Windows CI environment

This file is automatically added to the Python path during CI runs to ensure
that the VB-Audio Virtual Cable device is properly selected with WDM-KS drivers
instead of the default MME drivers, which have compatibility issues on
Windows Server 2025 (the new GitHub runner image).
"""

import sys

try:
    import sounddevice as sd

    # Query available devices and host APIs
    devs = sd.query_devices()
    has = sd.query_hostapis()

    def host_name(d):
        return has[d["hostapi"]]["name"]

    # Find WDM-KS devices with 'CABLE Output' in the name
    candidates = [
        i
        for i, d in enumerate(devs)
        if d.get("max_input_channels", 0) > 0
        and "CABLE Output" in d.get("name", "")
        and host_name(d) == "Windows WDM-KS"
    ]

    if candidates:
        idx = candidates[0]
        try:
            # Set as input device only
            sd.default.device = (idx, None)
        except Exception:
            # Fallback to setting for both input/output
            sd.default.device = idx

        sys.stderr.write(
            f"[sitecustomize] WDM-KS input -> #{idx}: {devs[idx]['name']}\n"
        )
    else:
        sys.stderr.write("[sitecustomize] No WDM-KS 'CABLE Output' found.\n")

except Exception as e:
    sys.stderr.write(f"[sitecustomize] skip: {e}\n")
