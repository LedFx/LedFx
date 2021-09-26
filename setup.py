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
    "numpy>=1.20.2",
    "wheel>=0.36.2",
]

INSTALL_REQUIRES = [
<<<<<<< HEAD
    "numpy~=1.20.2",
=======
>>>>>>> frontend_beta
    "voluptuous~=0.12.1",
    "sounddevice~=0.4.2",
    "sacn~=1.6.3",
    "aiohttp~=3.7.4.post0",
    "multidict~=5.0.0",
<<<<<<< HEAD
    "requests~=2.24.0",
=======
    "requests>=2.24.0",
>>>>>>> frontend_beta
    "aubio~=0.4.9",
    "zeroconf==0.30.0",
    "cython>=0.29.21",
    "pyupdater>=3.1.0",
    "sentry-sdk~=1.0.0",
    "certifi>=2020.12.5",
    "pyserial>=3.5",
    "pystray>=0.17",
    "tcp-latency>=0.0.10",
    "mido>=1.2.10",
    "python-rtmidi>=1.4.9",
    "aiohttp_cors>=0.7.0",
    "paho-mqtt>=1.5.1",
    "yappi",
    "psutil>=5.8.0",
    # Conditional Requirement
    # We need pywin32 for Windows
    'pywin32>=300; platform_system == "Windows"',
    # uvloop doesn't work on Windows yet, but should be a good speedup for low power linux devices
    'uvloop>=0.16.0; platform_system != "Windows"',
    # We can install this on all linux devices, it just won't work for anything other than a Pi
    'rpi-ws281x>=4.3.0; platform_system == "Linux"',
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
