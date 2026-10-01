from ledfx.effects.droplets import DROPLET_NAMES, _create_name


def test_droplet_names_are_sorted_for_a_stable_schema() -> None:
    assert list(DROPLET_NAMES) == sorted(DROPLET_NAMES)
    assert "Ripple" in DROPLET_NAMES  # rain's default


def test_create_name_strips_only_the_suffix() -> None:
    assert _create_name("puppy_dog.npy") == "Puppy Dog"
