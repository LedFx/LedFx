
import asyncio

from typing import Any, Optional, cast
import logging
from zeroconf import  ServiceStateChange, Zeroconf
from zeroconf.asyncio import (
    AsyncServiceBrowser,
    AsyncServiceInfo,
    AsyncZeroconf,
    
)
from ledfx.utils import async_fire_and_forget
_LOGGER = logging.getLogger(__name__)

class WLEDResponder:

    def async_on_service_state_change(
        zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange
    ) -> None:
        print(f"Service {name} of type {service_type} state changed: {state_change}")
        if state_change is not ServiceStateChange.Added:
            return
        async_fire_and_forget(WLEDResponder.async_display_service_info(zeroconf, service_type, name))


    async def async_display_service_info(zeroconf: Zeroconf, service_type: str, name: str) -> None:
        info = AsyncServiceInfo(service_type, name)
        await info.async_request(zeroconf, 3000)
        print("Info from zeroconf.get_service_info: %r" % (info))
        if info:
            addresses = ["%s:%d" % (addr, cast(int, info.port)) for addr in info.parsed_scoped_addresses()]
            print("  Name: %s" % name)
            print("  Addresses: %s" % ", ".join(addresses))
            print("  Weight: %d, priority: %d" % (info.weight, info.priority))
            print(f"  Server: {info.server}")
            if info.properties:
                print("  Properties are:")
                for key, value in info.properties.items():
                    print(f"    {key!r}: {value!r}")
            else:
                print("  No properties")
        else:
            print("  No info")
        print('\n')


class ZeroConfRunner:

    def __init__(self, args: Any) -> None:
        self.args = args
        self.aiobrowser: Optional[AsyncServiceBrowser] = None
        self.aiozc: Optional[AsyncZeroconf] = None

    async def async_run(self) -> None:
        self.aiozc = AsyncZeroconf()

        services = ["_wled._tcp.local."]

        print("\nBrowsing %s service(s), press Ctrl-C to exit...\n" % services)
        self.aiobrowser = AsyncServiceBrowser(
            self.aiozc.zeroconf, services, handlers=[WLEDResponder.async_on_service_state_change]
        )


    async def async_close(self) -> None:
        assert self.aiozc is not None
        assert self.aiobrowser is not None
        await self.aiobrowser.async_cancel()
        await self.aiozc.async_close()