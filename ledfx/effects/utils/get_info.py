import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)


async def fetch_info(session, ip_address, callback):
    """Fetches WLED device information asynchronously."""
    url = f"http://{ip_address}/json/info"
    try:
        timeout = aiohttp.ClientTimeout(total=0.8)
        async with session.get(url, timeout=timeout) as response:
            data = await response.json()
            callback(data)
    except Exception as e:
        _LOGGER.warning(f"Error fetching info from {ip_address}: {e}")


# A wrapper that launches the request asynchronously
def get_info_async(loop, ip_address, callback):
    """Launches an asynchronous request to fetch WLED device information."""
    try:
        loop.create_task(_start_request(ip_address, callback))
    except RuntimeError as e:
        _LOGGER.warning(f"Error creating task in the provided loop: {e}")


# Internal coroutine to be launched as a task
async def _start_request(ip_address, callback):
    """Internal coroutine to fetch WLED device information."""
    async with aiohttp.ClientSession() as session:
        await fetch_info(session, ip_address, callback)


