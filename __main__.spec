# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['C:\\Users\\mb\\Python\\LedFx/ledfx/__main__.py'],
             pathex=['C:\\ProgramData\\Anaconda3\\pkgs*', 'C:\\Users\\mb\\Python\\LedFx'],
             binaries=[],
             datas=[('C:\\Users\\mb\\Python\\LedFx/ledfx_frontend', 'ledfx_frontend/'), ('C:\\Users\\mb\\Python\\LedFx/ledfx', 'ledfx/')],
             hiddenimports=['sacn', 'pyaudio', 'portaudio', 'aubio', 'numpy', 'math', 'voluptuous', 'numpy'],
             hookspath=[],
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
          name='__main__',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True , icon='C:\\Users\\mb\\Python\\LedFx\\icons\\discord.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='__main__')
