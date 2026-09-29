import json

from ledfx.api.jsonutil import dumps
from ledfx.configuration.models import LedFxConfig


def test_dumps_serialises_models_inside_plain_structures() -> None:
    cfg = LedFxConfig()
    out = json.loads(dumps({"audio": cfg.audio, "scenes": cfg.scenes, "n": 1}))
    assert out["audio"]["min_volume"] == 0.2 and out["n"] == 1
