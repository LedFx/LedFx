"""
PyInstaller hook for aubio-ledfx.

This hook ensures that all DLLs bundled with aubio-ledfx (via delvewheel on Windows)
are properly collected and included in the frozen binary.
"""
from PyInstaller.utils.hooks import collect_dynamic_libs, get_module_file_attribute
import os
import sys

# Collect all dynamic libraries from aubio package
binaries = collect_dynamic_libs('aubio')

# On Windows, delvewheel bundles DLLs in a .libs folder next to the package
if sys.platform == 'win32':
    try:
        aubio_path = get_module_file_attribute('aubio')
        if aubio_path:
            aubio_dir = os.path.dirname(aubio_path)
            libs_dir = os.path.join(aubio_dir, '.libs')
            
            if os.path.exists(libs_dir):
                # Add all DLL files from the .libs directory
                for filename in os.listdir(libs_dir):
                    if filename.endswith('.dll'):
                        dll_path = os.path.join(libs_dir, filename)
                        binaries.append((dll_path, '.'))
    except Exception:
        pass

# Ensure the _aubio module is collected
hiddenimports = ['aubio._aubio']

datas = []
