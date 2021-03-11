#!/usr/bin/env python3

from setuptools import setup

import ledfx.consts as const

PROJECT_PACKAGE_NAME = "ledfx"
PROJECT_VERSION = const.PROJECT_VERSION
PROJECT_LICENSE = "The MIT License"
PROJECT_AUTHOR = "Austin Hodges"
PROJECT_AUTHOR_EMAIL = "austin.b.hodges@gmail.com"
PROJECT_MAINTAINER = "LedFx Developers"
PROJECT_MAINTAINER_EMAIL = "ledfx.app@gmail.com"
PROJECT_URL = "https://github.com/LedFx/LedFx/tree/dev"

# Need to install numpy first
SETUP_REQUIRES = [
    "numpy>=1.20.1",
]

INSTALL_REQUIRES = [
    "numpy>=1.20.1",
    "voluptuous>=0.12.0",
    "pyaudio>=0.2.11",
    "sacn>=1.5",
    "aiohttp>=3.7.4.post0",
    "yarl>=1.5.1",
    "multidict>=5.0.0",
    "aiohttp_jinja2>=1.1.0",
    "requests>=2.24.0",
    "aubio>=0.4.9",
    "zeroconf>=0.28.6",
    'pypiwin32>=223; platform_system == "Windows"',
    "cython>=0.29.21",
    "pyupdater>=3.1.0",
    "sentry-sdk>=1.0.0",
    "certifi>=2019.3.9",
    "pyserial>=3.5",
    "pystray>=0.17",
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
        "Documentation": "https://ledfx.readthedocs.io/en/docs/index.html",
        "Website": "https://ledfx.app",
        "Source": "https://github.com/LedFx/LedFx",
        "Discord": "https://discord.gg/PqXMuthSNx",
    },
    install_requires=INSTALL_REQUIRES,
    setup_requires=SETUP_REQUIRES,
    python_requires=const.REQUIRED_PYTHON_STRING,
    entry_points={"console_scripts": ["ledfx = ledfx.__main__:main"]},
)
