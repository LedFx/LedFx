def probe(names: list[str]) -> list[str]:
    return [f"{n}!" for n in names if n != ""]
