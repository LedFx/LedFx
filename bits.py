# HOW TO DEBUG METHODS

_LOGGER.info(" - Available methods:")
for mName in sorted(dir(effect)):
    if mName.find("__") >= 0:
        continue

    if callable(getattr(effect, mName)):
        _LOGGER.info(f"     {mName}()")
