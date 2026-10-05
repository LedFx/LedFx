"""The application native E1.31 adapter works without historical libraries."""

import subprocess
import sys
import tomllib
from pathlib import Path


def test_runtime_has_no_historical_dependency() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())
    dependencies = project["project"]["dependencies"]
    assert not any(
        package.startswith(("sacn", "stupidartnet", "python-osc"))
        for package in dependencies
    )


def test_native_adapter_sends_with_historical_imports_blocked() -> None:
    script = """
import importlib.abc, sys
from unittest.mock import MagicMock
class BlockHistorical(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('sacn', 'stupidArtnet', 'pythonosc'):
            raise ModuleNotFoundError('historical dependency intentionally unavailable')
sys.meta_path.insert(0, BlockHistorical())
from ledfx_senders import E131Sender
from ledfx.devices.e131 import E131Device
from tests.e131_helpers import decode_packet
config = E131Device.Config.model_validate(
    {'name': 'test', 'ip_address': '127.0.0.1', 'pixel_count': 60}
)
device = E131Device(MagicMock(), config)
sender = E131Sender._test_sender(
    device._layout(), destination='127.0.0.1', source_name='test', mode='capture'
)
try:
    device._sender = sender
    device.flush(bytes([17, 34, 51]) * 60)
    packet = sender._engine.captures()[0][0]
    fields = decode_packet(packet)
    assert fields['universe'] == 1
    assert fields['payload'] == bytes([17, 34, 51]) * 60 + bytes(512 - 180)
finally:
    sender.close(False)
"""
    subprocess.run([sys.executable, "-c", script], check=True, timeout=10)
