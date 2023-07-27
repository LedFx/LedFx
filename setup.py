#!/usr/bin/env python3

from setuptools import setup

import ledfx.consts as const

PROJECT_DOCS = "https://ledfx.readthedocs.io"
PROJECT_PACKAGE_NAME = "ledfx"
PROJECT_VERSION = const.PROJECT_VERSION
PROJECT_LICENSE = "The MIT License"
PROJECT_AUTHOR = "Austin Hodges"
PROJECT_AUTHOR_EMAIL = "austin.b.hodges@gmail.com"
PROJECT_MAINTAINER = "LedFx Developers"
PROJECT_MAINTAINER_EMAIL = "ledfx.app@gmail.com"
PROJECT_URL = "https://github.com/LedFx/LedFx"
PROJECT_WEBSITE = "https://ledfx.app"
PROJECT_DOCS = "https://ledfx.readthedocs.io"

# Need to install numpy first
SETUP_REQUIRES = [
    "numpy~=1.23",
    "wheel>=0.36.2",
]

INSTALL_REQUIRES = [
    "aiohttp~=3.8.3",
    "aiohttp_cors>=0.7.0",
    "aubio>=0.4.9",
    "cython>=0.29.21",
    "certifi>=2020.12.5",
    "multidict~=5.0.0",
    "openrgb-python~=0.2.10",
    "paho-mqtt>=1.5.1",
    "psutil>=5.8.0",
    "pyserial>=3.5",
    "pystray>=0.17",
    "python-rtmidi~=1.5.3",
    "requests~=2.28.2",
    "sacn~=1.6.3",
    "sentry-sdk==1.14.0",
    "sounddevice~=0.4.2",
    "samplerate>=0.1.0",
    "icmplib~=3.0.3",
    "voluptuous~=0.12.1",
    "zeroconf~=0.39.4",
    "pillow>=8.4.0",
    # Conditional Requirement
    # We need pywin32 for Windows
    'pywin32>=302; platform_system == "Windows"',
    # uvloop doesn't work on Windows yet, but should be a good speedup for low power linux devices
    'uvloop>=0.16.0; platform_system != "Windows"',
    # We can install this on all linux devices, it just won't work for anything other than a Pi
    'rpi-ws281x>=4.3.0; platform_system == "Linux"',
    "flux-led>=0.28.35",
    "python-mbedtls~=2.7.1",
]


setup(
    name=PROJECT_PACKAGE_NAME,
    version=PROJECT_VERSION,
    license=PROJECT_LICENSE,
    author=PROJECT_AUTHOR,
    author_email=PROJECT_AUTHOR_EMAIL,
    maintainer=PROJECT_MAINTAINER,
    maintainer_email=PROJECT_MAINTAINER_EMAIL,
    url=PROJECT_URL,
    project_urls={
        "Documentation": PROJECT_DOCS,
        "Website": PROJECT_WEBSITE,
        "Source": PROJECT_URL,
        "Discord": "https://discord.gg/PqXMuthSNx",
    },
    install_requires=INSTALL_REQUIRES,
    setup_requires=SETUP_REQUIRES,
    python_requires=const.REQUIRED_PYTHON_STRING,
    entry_points={"console_scripts": ["ledfx = ledfx.__main__:main"]},
)
