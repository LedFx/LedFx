from ledfx.scenes import Scenes


class _DummyEvents:
    def fire_event(self, *_, **__):
        pass


class _DummyVirtual:
    def __init__(self, virtual_id, effect=None):
        self.id = virtual_id
        self.active_effect = effect


class _DummyEffect:
    def __init__(self, effect_type, config):
        self.type = effect_type
        self.config = config


class _DummyLedFx:
    def __init__(self, scenes=None, virtuals=None):
        self.config_dir = ""
        self.config = {"scenes": scenes or {}}
        self.virtuals = virtuals or {}
        self.events = _DummyEvents()


def _build_scenes_manager(scene_config, virtuals):
    dummy_ledfx = _DummyLedFx(scenes=scene_config, virtuals=virtuals)
    return Scenes(dummy_ledfx)


def test_scene_is_active_when_effects_match():
    scene_id = "scene-one"
    scenes = {
        scene_id: {
            "name": "Scene One",
            "virtuals": {
                "v1": {"type": "bars", "config": {"speed": 2}},
                "v2": {},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 2})),
        "v2": _DummyVirtual("v2", None),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is True


def test_scene_is_not_active_on_effect_mismatch():
    scene_id = "scene-two"
    scenes = {
        scene_id: {
            "name": "Scene Two",
            "virtuals": {
                "v1": {"type": "bars", "config": {"speed": 2}},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 3})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is False


def test_scene_is_not_active_when_virtual_missing():
    scene_id = "scene-three"
    scenes = {
        scene_id: {
            "name": "Scene Three",
            "virtuals": {
                "ghost": {"type": "sparkle", "config": {"color": "red"}},
            },
        }
    }

    manager = _build_scenes_manager(scenes, virtuals={})

    assert manager.is_active(scene_id) is False
