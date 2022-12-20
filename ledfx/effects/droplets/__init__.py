import os

import numpy as np


def _create_name(filename: str) -> str:
    return filename.strip(".npy").replace("_", " ").title()


files = os.listdir(os.path.dirname(__file__))

DROPLETS = {
    _create_name(file): file for file in files if file.endswith(".npy")
}

DROPLET_NAMES = tuple(DROPLETS.keys())


def load_droplet(droplet_name: str) -> np.ndarray:
    return np.load(
        os.path.join(os.path.dirname(__file__), DROPLETS[droplet_name])
    )
