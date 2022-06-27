# -*- mode: python ; coding: utf-8 -*-
import os

spec_root = os.path.abspath(SPECPATH)

venv_root = os.path.abspath(os.path.join(SPECPATH, '..'))
block_cipher = None
print(venv_root)


a = Analysis([f'{spec_root}\\ledfx\\__main__.py'],
             pathex=[f'{spec_root}', f'{spec_root}\\ledfx'],
             binaries=[],
             datas=[(f'{spec_root}/ledfx_frontend', 'ledfx_frontend/'), (f'{spec_root}/ledfx/', 'ledfx/'), (f'{spec_root}/icons', 'icons/'),(f'{spec_root}/icons/tray.png','.')],
             hiddenimports=['sacn', 'aubio', 'numpy', 'math', 'voluptuous', 'numpy', 'aiohttp', 'mido','mido.frozen', 'paho', 'paho.mqtt', 'openrgb-python', 'openrgb', 'python-rtmidi','rtmidi', 'mido.backends.rtmidi', 'paho.mqtt.client','samplerate','_samplerate_data', 'sounddevice',
             'sentry_sdk', 'sentry_sdk.integrations.django','sentry_sdk.integrations.flask','sentry_sdk.integrations.bottle','sentry_sdk.integrations.falcon','sentry_sdk.integrations.sanic',
             'sentry_sdk.integrations.celery','sentry_sdk.integrations.aiohttp','sentry_sdk.integrations.rq','sentry_sdk.integrations.tornado','sentry_sdk.integrations.sqlalchemy',
             'sentry_sdk.integrations.boto3','_cffi_backend','serial','pystray._win32','serial.tools.list_ports','tcp_latency','aiohttp_cors','psutil','yappi'],
             hookspath=[f'{venv_root}\\lib\\site-packages\\pyupdater\\hooks'],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='LedFx',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          icon=f'{spec_root}\\icons\\discord.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='LedFx')
