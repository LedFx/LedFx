"""GET /system: clients detect v2 by this route answering 200."""

from ledfx.api.v2.core.router import Router
from ledfx.api.v2.models.system import SystemInfo
from ledfx.consts import PROJECT_VERSION

router = Router(tag="system")


@router.get("/system")
async def get_system() -> SystemInfo:
    """Get the server's name, version and API versions."""
    return SystemInfo(
        name="LedFx Controller", version=PROJECT_VERSION, api_versions=["v1", "v2"]
    )
