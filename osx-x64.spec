# -*- mode: python ; coding: utf-8 -*-
import os
from hiddenimports import hiddenimports
from ledfx.consts import PROJECT_VERSION
spec_root = os.path.abspath(SPECPATH)

venv_root = os.path.abspath(os.path.join(SPECPATH, '..'))
block_cipher = None


# Create prod.env for the packaged binaries to read from
with open('prod.env', 'w') as file:
    file.write('IS_RELEASE = true')
# move the prod.env file down one level
os.move("prod.env", f"{spec_root}/prod.env")


a = Analysis([f'{spec_root}\\ledfx\\__main__.py'],
             pathex=[f'{spec_root}', f'{spec_root}\\ledfx'],
             binaries=[],
             datas=[(f'{spec_root}/ledfx_frontend', 'ledfx_frontend/'), (f'{spec_root}/ledfx/', 'ledfx/'), (f'{spec_root}/ledfx_assets', 'ledfx_assets/'),(f'{spec_root}/ledfx_assets/tray.png','.'), (f'{spec_root}/prod.env','.')],
             hiddenimports=hiddenimports,
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
          icon=f'{spec_root}\\ledfx_assets\\discord.ico')

app = BUNDLE(exe,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='LedFx',
          icon=f'{spec_root}/ledfx_assets/logo.icns',
          bundle_identifier='com.ledfx.ledfx',
          version=f'{PROJECT_VERSION}',
          info_plist={
              'CFBundleShortVersionString': f'{PROJECT_VERSION}',
              'CFBundleVersion': f'{PROJECT_VERSION}',
              'LSApplicationCategoryType': 'public.app-category.music',
              'NSHumanReadableCopyright': 'Copyright © 2024 LedFx Developers',
              'NSPrincipalClass': 'NSApplication',
              'NSAppleScriptEnabled': False,
              'NSMicrophoneUsageDescription': 'LedFx uses audio for sound visualization',
              'com.apple.security.device.audio-input': True,
              'com.apple.security.device.microphone': True,
              },
          entitlements_plist={
              'com.apple.security.device.audio-input': True,
              'com.apple.security.device.microphone': True,
              })
# Cleanup prod.env
os.remove("prod.env")