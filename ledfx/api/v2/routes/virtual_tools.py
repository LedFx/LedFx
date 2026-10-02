"""v2: actions over many virtuals, and a virtual's tools.

/virtuals/oneshot and /virtuals/force-color act on every virtual. They share
a depth with /virtuals/{virtual_id}, and aiohttp (like OpenAPI 3.1) matches
the fixed path first: DELETE /virtuals/oneshot ends every flash. Virtuals.add
refuses both ids (RESERVED_IDS), but a virtual that already has the id
"oneshot" (an older config, or a device's own virtual) cannot be deleted
through v2. Other methods on that id reach the virtual.
"""

from ledfx.api.v2.core.binding import LedFxDep
from ledfx.api.v2.core.router import Router
from ledfx.api.v2.models.ids import VirtualIdParam
from ledfx.api.v2.models.virtuals import (
    ApplyConfig,
    ApplyConfigCounts,
    Calibration,
    ClearEffects,
    CopyEffect,
    ForceColor,
    Highlight,
    Oneshot,
    SetEffectAll,
    SetEffectAllCounts,
    checked_config,
    effect_variant,
)
from ledfx.configuration.models import GlobalEffectUpdate, OneshotParams
from ledfx.configuration.models import Highlight as HighlightParams
from ledfx.configuration.plugin import PluginConfig
from ledfx.errors import NotFound

router = Router(tag="virtuals")


def _params(body: Oneshot) -> OneshotParams:
    return OneshotParams(
        color=body.color,
        ramp_ms=body.ramp_ms,
        hold_ms=body.hold_ms,
        fade_ms=body.fade_ms,
        brightness=body.brightness,
    )


@router.post("/virtuals/clear-effects", status=204, errors=[NotFound])
async def clear_effects(body: ClearEffects, ledfx: LedFxDep) -> None:
    """Blank the output of these virtuals (default: all).

    Runtime only: their stored effects come back when LedFx restarts. 404 if an
    id does not exist (nothing is cleared).
    """
    ledfx.virtuals.clear_all_effects(body.virtual_ids)


@router.post("/virtuals/apply-config", errors=[NotFound])
async def apply_effect_config(body: ApplyConfig, ledfx: LedFxDep) -> ApplyConfigCounts:
    """Write settings into every running effect that has them.

    A gradient also sets the colours sampled from it, except those given. Each
    running effect is counted as updated, skipped (it has none of the settings)
    or failed (it refused them). 404 if an id in virtual_ids does not exist
    (nothing is written).
    """
    update = GlobalEffectUpdate(
        gradient=body.gradient,
        background_color=body.background_color,
        background_brightness=body.background_brightness,
        brightness=body.brightness,
        flip=body.flip,
        mirror=body.mirror,
    )
    result = ledfx.virtuals.apply_global_config(update, body.virtual_ids)
    return ApplyConfigCounts(**result._asdict())


@router.post("/virtuals/set-effect", errors=[NotFound])
async def set_effect_on_virtuals(
    body: SetEffectAll, ledfx: LedFxDep
) -> SetEffectAllCounts:
    """Start one effect on these virtuals (default: all).

    Without config the type's defaults start. An unknown virtual id is a 404
    and nothing starts. A virtual that refuses the effect (no segments) counts
    as failed; with fallback_s, one that is being streamed to counts as
    blocked.
    """
    variant = effect_variant(body.type)
    config = None
    if body.config is not None:
        config = PluginConfig.model_validate(
            checked_config(variant, body.config, body.config)
        )
    result = ledfx.virtuals.set_effect_all(
        body.type, config, body.virtual_ids, fallback=body.fallback_s
    )
    return SetEffectAllCounts(
        applied=result.applied, blocked=result.blocked, failed=result.failed
    )


@router.post("/virtuals/{virtual_id}/oneshot", status=204)
async def flash_virtual(
    virtual_id: VirtualIdParam, body: Oneshot, ledfx: LedFxDep
) -> None:
    """Flash the virtual with a colour (409 if it is not active)."""
    ledfx.virtuals.oneshot(virtual_id, _params(body))


@router.delete("/virtuals/{virtual_id}/oneshot", status=204)
async def clear_virtual_oneshots(virtual_id: VirtualIdParam, ledfx: LedFxDep) -> None:
    """End the virtual's flashes."""
    ledfx.virtuals.clear_oneshots(virtual_id)


@router.post("/virtuals/oneshot", status=204)
async def flash_virtuals(body: Oneshot, ledfx: LedFxDep) -> None:
    """Flash every active virtual with a colour."""
    ledfx.virtuals.oneshot(None, _params(body))


@router.delete("/virtuals/oneshot", status=204)
async def clear_oneshots(ledfx: LedFxDep) -> None:
    """End every virtual's flashes."""
    ledfx.virtuals.clear_oneshots(None)


@router.post("/virtuals/{virtual_id}/force-color", status=204)
async def force_virtual_color(
    virtual_id: VirtualIdParam, body: ForceColor, ledfx: LedFxDep
) -> None:
    """Fill the virtual with a colour until its effect draws again."""
    ledfx.virtuals.force_color(virtual_id, body.color)


@router.post("/virtuals/force-color", status=204)
async def force_color(body: ForceColor, ledfx: LedFxDep) -> None:
    """Fill every device's own virtual with a colour."""
    ledfx.virtuals.force_color(None, body.color)


@router.put("/virtuals/{virtual_id}/calibration", status=204)
async def set_calibration(
    virtual_id: VirtualIdParam, body: Calibration, ledfx: LedFxDep
) -> None:
    """Turn calibration mode, where highlights show, on or off."""
    ledfx.virtuals.set_calibration(virtual_id, body.enabled)


@router.put("/virtuals/{virtual_id}/highlight", status=204)
async def set_highlight(
    virtual_id: VirtualIdParam, body: Highlight, ledfx: LedFxDep
) -> None:
    """Light a device's pixels on a calibrating virtual (409 otherwise)."""
    ledfx.virtuals.set_highlight(
        virtual_id, HighlightParams(body.device_id, body.start, body.end, body.flip)
    )


@router.delete("/virtuals/{virtual_id}/highlight", status=204)
async def clear_highlight(virtual_id: VirtualIdParam, ledfx: LedFxDep) -> None:
    """Turn the highlight off (204 whether or not the virtual is calibrating)."""
    ledfx.virtuals.set_highlight(virtual_id, None)


@router.post("/virtuals/{virtual_id}/copy-effect", status=204, errors=[NotFound])
async def copy_effect(
    virtual_id: VirtualIdParam, body: CopyEffect, ledfx: LedFxDep
) -> None:
    """Start this virtual's effect, with its settings, on the targets.

    404 if a target does not exist (nothing is copied). Targets that refuse
    the effect are passed over; 409 if none takes it, or if this virtual runs
    nothing.
    """
    ledfx.virtuals.copy_effect(virtual_id, body.targets)
