import os

import numpy as np


def _create_name(filename: str) -> str:
    return filename.removesuffix(".npy").replace("_", " ").title()


# Sorted: os.listdir order is filesystem-dependent, and the enum order is API.
files = sorted(os.listdir(os.path.dirname(__file__)))

DROPLETS = {_create_name(file): file for file in files if file.endswith(".npy")}

DROPLET_NAMES = tuple(DROPLETS.keys())


def load_droplet(droplet_name: str) -> np.ndarray:
    return np.load(os.path.join(os.path.dirname(__file__), DROPLETS[droplet_name]))
