#!/usr/bin/env python3

from datetime import datetime as dt
from setuptools import setup, find_packages
import ledfx.consts as const

PROJECT_PACKAGE_NAME = 'ledfx-dev'
PROJECT_VERSION = const.PROJECT_VERSION
PROJECT_LICENSE = 'The MIT License'
PROJECT_AUTHOR = 'Austin Hodges'
PROJECT_AUTHOR_EMAIL = 'austin.b.hodges@gmail.com'
PROJECT_MAINTAINER = 'LedFx Devs'
PROJECT_MAINTAINER_EMAIL = 'ledfx.app@gmail.com'
PROJECT_URL = 'https://github.com/ahodges9/LedFx/tree/dev'

# Need to install numpy first
SETUP_REQUIRES = [
    'numpy==1.19.3'
]

INSTALL_REQUIRES = [
    # Nasty bug in windows 10 at the moment - https://developercommunity.visualstudio.com/content/problem/1207405/fmod-after-an-update-to-windows-2004-is-causing-a.html
    # numpy 1.19.3 has a workaround
    'numpy==1.19.3',
    'voluptuous==0.12.0',
    'pyaudio>=0.2.11',
    'sacn==1.4.6',
    # aiohttp 3.7 branch has a regression that spams errors - bug report https://github.com/aio-libs/aiohttp/issues/5212
    'aiohttp==3.6.3',
    # yarl needs to be this for aiohttp
    'yarl==1.5.1',
    # multidict needs to be this for aiohttp
    'multidict==4.7.6',
    'aiohttp_jinja2>=1.1.0',
    'requests>=2.24.0',
	'pyyaml>=5.3.1',
    'aubio>=0.4.9',
    'zeroconf>=0.28.6',
    'pypiwin32>=223;platform_system=="Windows"',
    'pyupdater>=3.1.1'
]

setup(
    name=PROJECT_PACKAGE_NAME,
    version=PROJECT_VERSION,
    license = PROJECT_LICENSE,
    author=PROJECT_AUTHOR,
    author_email=PROJECT_AUTHOR_EMAIL,
    maintainer=PROJECT_MAINTAINER,
    maintainer_email=PROJECT_MAINTAINER_EMAIL,
    url=PROJECT_URL,
    project_urls={
        'Documentation': 'https://ledfx.readthedocs.io/en/docs/index.html',
        'Website': 'https://ledfx.app',
        'Source': 'https://github.com/ahodges9/LedFx',
        'Discord': 'https://discord.gg/PqXMuthSNx'
    },
    install_requires=INSTALL_REQUIRES,
    setup_requires=SETUP_REQUIRES,
    python_requires=const.REQUIRED_PYTHON_STRING,
    include_package_data=True,
    # packages=find_packages(),
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'ledfx = ledfx.__main__:main'
        ]
    },
    package_data={
        'ledfx_frontend': ['*'],
        '': ['*.npy'],
        '': ['*.yaml']
    },
)
