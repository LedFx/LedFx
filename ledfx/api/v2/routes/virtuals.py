"""v2 virtuals: list, create, read, change and delete."""

from ledfx.api.v2.core.binding import LedFxDep
from ledfx.api.v2.core.partial import Partial
from ledfx.api.v2.core.router import Router
from ledfx.api.v2.models.ids import VirtualIdParam
from ledfx.api.v2.models.virtuals import Virtual, VirtualCreate, VirtualUpdate
from ledfx.configuration.models import VirtualConfig

router = Router(tag="virtuals")


@router.get("/virtuals")
async def list_virtuals(ledfx: LedFxDep) -> list[Virtual]:
    """List the virtuals."""
    return [Virtual.of(virtual) for virtual in ledfx.virtuals.values()]


@router.post("/virtuals", status=201)
async def create_virtual(body: VirtualCreate, ledfx: LedFxDep) -> Virtual:
    """Create a virtual.

    Its id is made from the name (lowercase, other characters as "-") and
    made unique with a numeric suffix. The new virtual has no segments.
    """
    config = VirtualConfig.model_validate(body.config.model_dump())
    return Virtual.of(ledfx.virtuals.add(config))


@router.get("/virtuals/{virtual_id}")
async def get_virtual(virtual_id: VirtualIdParam, ledfx: LedFxDep) -> Virtual:
    """Get a virtual."""
    return Virtual.of(ledfx.virtuals.get_or_raise(virtual_id))


@router.patch("/virtuals/{virtual_id}")
async def update_virtual(
    virtual_id: VirtualIdParam, body: Partial[VirtualUpdate], ledfx: LedFxDep
) -> Virtual:
    """Change a virtual's settings, segments or active state.

    Only the fields sent change; a config object merges into the current one,
    and segments replace the list. A stored setting that the change leaves
    alone but that is no longer valid gives 409.
    """
    return Virtual.of(ledfx.virtuals.patch(virtual_id, body))


@router.delete("/virtuals/{virtual_id}", status=204)
async def delete_virtual(virtual_id: VirtualIdParam, ledfx: LedFxDep) -> None:
    """Delete a virtual.

    A device's own virtual takes its device with it. Scenes forget it.
    """
    ledfx.virtuals.remove(virtual_id)
