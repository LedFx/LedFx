"""v2: a virtual's running effect and its effect history."""

from pydantic import BaseModel

from ledfx.api.v2.core.binding import LedFxDep
from ledfx.api.v2.core.router import Router
from ledfx.api.v2.models.ids import VirtualIdParam
from ledfx.api.v2.models.plugins import effect_state
from ledfx.api.v2.models.virtuals import (
    EffectHistoryItem,
    EffectPatch,
    EffectPut,
    TypeId,
    checked_config,
    current_effect,
    effect_variant,
)
from ledfx.configuration.plugin import PluginConfig
from ledfx.errors import Conflict, NotFound
from ledfx.virtuals import Virtual

router = Router(tag="virtuals")


def _shown(virtual: Virtual) -> BaseModel:
    state = current_effect(virtual)
    if state is None:
        raise Conflict(f"Virtual {virtual.id} has no active effect")
    return state


@router.get("/virtuals/{virtual_id}/effect")
async def get_effect(
    virtual_id: VirtualIdParam, ledfx: LedFxDep
) -> EffectHistoryItem | None:
    """Get the virtual's effect: its type and settings, or null.

    A stored effect whose type is no longer registered shows as an
    UnknownPlugin (available: false); it cannot run.
    """
    return current_effect(ledfx.virtuals.get_or_raise(virtual_id))


@router.put("/virtuals/{virtual_id}/effect")
async def set_effect(
    virtual_id: VirtualIdParam, body: EffectPut, ledfx: LedFxDep
) -> EffectHistoryItem:
    """Start an effect.

    config is checked against the type's settings; without it the settings
    this virtual last used for the type apply (409 if they no longer pass
    the type's checks). With fallback_s the current effect comes back after
    that many seconds (409 if the virtual is being streamed to). Starting an
    effect makes the virtual active.
    """
    ledfx.virtuals.get_or_raise(virtual_id)
    variant = effect_variant(body.type)
    config = None
    if body.config is not None:
        config = PluginConfig.model_validate(
            checked_config(variant, body.config, body.config)
        )
    virtual = ledfx.virtuals.set_effect(
        virtual_id, body.type, config, fallback=body.fallback_s
    )
    return _shown(virtual)


@router.patch("/virtuals/{virtual_id}/effect")
async def update_effect(
    virtual_id: VirtualIdParam, body: EffectPatch, ledfx: LedFxDep
) -> EffectHistoryItem:
    """Change some settings of the running effect.

    The settings are checked against the running effect's type. A colour
    change on an effect that blends colours restarts it, so it fades in.
    Restarting the effect makes the virtual active.
    """
    type_id, config = ledfx.virtuals.running_effect(virtual_id)
    variant = effect_variant(type_id)
    stored = {
        name: value
        for name, value in config.as_dict(mode="json").items()
        if name in variant.model_fields
    }
    patch = checked_config(variant, {**stored, **body.config}, body.config)
    return _shown(
        ledfx.virtuals.patch_effect(
            virtual_id, PluginConfig.model_validate(patch), type_id=type_id
        )
    )


@router.delete("/virtuals/{virtual_id}/effect", status=204)
async def clear_effect(virtual_id: VirtualIdParam, ledfx: LedFxDep) -> None:
    """Stop the effect. Its settings stay in the history."""
    ledfx.virtuals.clear_effect(virtual_id)


@router.post("/virtuals/{virtual_id}/effect/randomize")
async def randomize_effect(
    virtual_id: VirtualIdParam, ledfx: LedFxDep
) -> EffectHistoryItem:
    """Give the running effect random settings (brightness stays)."""
    return _shown(ledfx.virtuals.randomize_effect(virtual_id))


@router.post("/virtuals/{virtual_id}/effect/reset")
async def reset_effect(
    virtual_id: VirtualIdParam, ledfx: LedFxDep
) -> EffectHistoryItem:
    """Restart the running effect with its default settings."""
    return _shown(ledfx.virtuals.reset_effect(virtual_id))


@router.get("/virtuals/{virtual_id}/effects")
async def list_effect_history(
    virtual_id: VirtualIdParam, ledfx: LedFxDep
) -> list[EffectHistoryItem]:
    """List the settings the virtual last used for each effect type."""
    return [
        effect_state(type_id, config.as_dict(mode="json"))
        for type_id, config in ledfx.virtuals.effect_history(virtual_id)
    ]


@router.delete("/virtuals/{virtual_id}/effects/{effect_type}", status=204)
async def delete_effect_history(
    virtual_id: VirtualIdParam, effect_type: TypeId, ledfx: LedFxDep
) -> None:
    """Forget an effect type's settings, stopping it if it is running."""
    history = ledfx.virtuals.effect_history(virtual_id)
    if effect_type not in [type_id for type_id, _ in history]:
        raise NotFound("Effect", effect_type)
    ledfx.virtuals.delete_effect_history(virtual_id, effect_type)


@router.post("/virtuals/{virtual_id}/fallback", status=204)
async def fire_fallback(virtual_id: VirtualIdParam, ledfx: LedFxDep) -> None:
    """End a temporary (fallback_s) effect now: the previous one comes back."""
    ledfx.virtuals.fire_fallback(virtual_id)
