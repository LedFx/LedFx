# -*- mode: python ; coding: utf-8 -*-
import os
from hiddenimports import hiddenimports
spec_root = os.path.abspath(SPECPATH)

venv_root = os.path.abspath(os.path.join(SPECPATH, '..'))
block_cipher = None


# if this is a release, create prod.env for the packaged binaries to read from and hide the console
github_ref = os.getenv('GITHUB_REF')
if github_ref and 'refs/tags/' in github_ref:
    with open('prod.env', 'w') as file:
        file.write('IS_RELEASE = true')
    SHOW_CONSOLE = False
else:
    with open('prod.env', 'w') as file:
        file.write('IS_RELEASE = false')
    SHOW_CONSOLE = True
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
          console=SHOW_CONSOLE,
          icon=f'{spec_root}\\ledfx_assets\\discord.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='LedFx')

# Cleanup prod.env
os.remove("prod.env")