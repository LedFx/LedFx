import os
import shutil
from pathlib import Path
from sys import platform


def copy_lib():
    file_path = os.path.realpath(__file__)
    file_head, _ = os.path.split(file_path)
    # Check if Windows.
    if platform != "win32":
        print("This is only supported for Windows.")
        return
    # Check if this script running is already in site packages, in which case
    # just go back by one and get the sounddevice_data dir.
    lib_path = ""
    for p in Path(file_head).parts:
        if p == "site-packages":
            lib_path = os.path.join(
                file_head,
                os.pardir,
                "_sounddevice_data",
                "portaudio-binaries",
                "libportaudio64bit.dll",
            )
            break

    # If not in site-packages, means it's a development environment, so get env path from the .venv
    if not lib_path:
        lib_path = os.path.join(
            ".venv",
            "Lib",
            "site-packages",
            "_sounddevice_data",
            "portaudio-binaries",
            "libportaudio64bit.dll",
        )
    try:
        shutil.copy(
            os.path.join("loopback", "libportaudio64bit.dll"),
            os.path.abspath(lib_path),
        )
    except FileNotFoundError:
        print(
            "Directory for dll was not found, make sure the install was successful."
        )
