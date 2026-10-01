"""POST /api/get_nanoleaf_token: only well-formed LAN addresses are contacted."""

import io
import json
import urllib.error
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ledfx.api import get_nanoleaf_token
from ledfx.api.get_nanoleaf_token import GetNanoleadTokenEndpoint


class _Request:
    def __init__(self, data):
        self._data = data

    async def json(self):
        return self._data


async def _post(ip, port):
    endpoint = GetNanoleadTokenEndpoint(SimpleNamespace(thread_executor=None))
    with patch.object(get_nanoleaf_token, "safe_urlopen") as urlopen:
        urlopen.return_value = io.BytesIO(b'{"auth_token": "abc"}')
        resp = await endpoint.post(_Request({"ip_address": ip, "port": port}))
    return json.loads(resp.body), urlopen


@pytest.mark.parametrize(
    "ip",
    [
        "evil.example/steal?",
        "evil.example#",
        "user@192.168.1.5",
        "http://192.168.1.5",
        "192.168.1.5:80",
        "192.168.1.5/admin",
        "a b",
        "-bad.local",
        "",
        12345,
        None,
    ],
)
async def test_malformed_host_is_rejected(ip):
    body, urlopen = await _post(ip, 16021)
    assert body["status"] == "failed"
    urlopen.assert_not_called()


@pytest.mark.parametrize("port", [0, 65536, -1, "abc", "80/x", True, 1.5, None])
async def test_malformed_port_is_rejected(port):
    body, urlopen = await _post("192.168.1.5", port)
    assert body["status"] == "failed"
    urlopen.assert_not_called()


@pytest.mark.parametrize(
    "ip", ["127.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1", "0.0.0.0"]
)
async def test_loopback_and_link_local_are_rejected(ip):
    body, urlopen = await _post(ip, 16021)
    assert body["status"] == "failed"
    urlopen.assert_not_called()


@pytest.mark.parametrize(
    ("ip", "port", "url"),
    [
        ("192.168.1.5", 16021, "http://192.168.1.5:16021/api/v1/new"),
        ("10.0.0.7", "16021", "http://10.0.0.7:16021/api/v1/new"),
        ("fd00::5", 16021, "http://[fd00::5]:16021/api/v1/new"),
    ],
)
async def test_lan_device_is_contacted(ip, port, url):
    body, urlopen = await _post(ip, port)
    assert body == {"auth_token": "abc"}
    request = urlopen.call_args.args[0]
    assert request.full_url == url
    assert request.get_method() == "POST"
    assert urlopen.call_args.kwargs["allow_private"] is True


@pytest.mark.parametrize(
    "host",
    ["nanoleaf.local", "Nanoleaf-Light-Panels-5F-A3.local.", "my_panel", "nl1"],
)
def test_hostnames_are_accepted(host):
    assert get_nanoleaf_token.is_valid_host(host)


async def test_not_in_pairing_mode_reports_pairing_hint():
    endpoint = GetNanoleadTokenEndpoint(SimpleNamespace(thread_executor=None))
    err = urllib.error.HTTPError("u", 403, "Forbidden", None, None)  # type: ignore[arg-type]
    with patch.object(get_nanoleaf_token, "safe_urlopen", side_effect=err):
        resp = await endpoint.post(
            _Request({"ip_address": "192.168.1.5", "port": 16021})
        )
    assert "pairing mode" in json.loads(resp.body)["payload"]["reason"]
