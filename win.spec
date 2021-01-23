# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['C:\\Users\\shaun\\ledfx_venv_3.9\\ledfx\\ledfx\\__main__.py'],
             pathex=['C:\\Users\\shaun\\ledfx_venv_3.9\\ledfx', 'C:\\Users\\shaun\\ledfx_venv_3.9\\ledfx\\ledfx'],
             binaries=[],
             datas=[('C:/Users/shaun/ledfx_venv_3.9/ledfx/ledfx_frontend', 'ledfx_frontend/'), ('C:/Users/shaun/ledfx_venv_3.9/ledfx/ledfx/', 'ledfx/'), ('C:/Users/shaun/ledfx_venv_3.9/ledfx/icons', 'icons/')],
             hiddenimports=['sacn', 'pyaudio', 'aubio', 'numpy', 'math', 'voluptuous', 'numpy', 'aiohttp', 'aiohttp_jinja2',
             'sentry_sdk', 'sentry_sdk.integrations.django','sentry_sdk.integrations.flask','sentry_sdk.integrations.bottle','sentry_sdk.integrations.falcon','sentry_sdk.integrations.sanic',
             'sentry_sdk.integrations.celery','sentry_sdk.integrations.aiohttp','sentry_sdk.integrations.rq','sentry_sdk.integrations.tornado','sentry_sdk.integrations.sqlalchemy',
             'sentry_sdk.integrations.boto3','_cffi_backend','serial'],
             hookspath=['c:\\users\\shaun\\ledfx\\lib\\site-packages\\pyupdater\\hooks'],
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
          name='win',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='win')
