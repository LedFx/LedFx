import os

import tomli
import ledfx_assets

# Get the path to pyproject.toml file
pyproject_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "pyproject.toml"
)

# Read the pyproject.toml file
with open(pyproject_path, "rb") as file:
    toml_data = tomli.load(file)

# Access the values from pyproject dict
# To bump version, update pyproject.toml

PROJECT_VERSION = toml_data["tool"]["poetry"]["version"]
PROJECT_NAME = toml_data["tool"]["poetry"]["name"]
PROJECT_AUTHOR = toml_data["tool"]["poetry"]["authors"][0]
PROJECT_LICENSE = toml_data["tool"]["poetry"]["license"]
CONFIG_MAJOR_VERSION = 2
CONFIG_MINOR_VERSION = 2
CONFIG_MICRO_VERSION = 0
# Dev turns sentry logging on and off
DEV = 0

CONFIGURATION_VERSION = "{}.{}.{}".format(
    CONFIG_MAJOR_VERSION, CONFIG_MINOR_VERSION, CONFIG_MICRO_VERSION
)
LEDFX_ASSETS_PATH = ledfx_assets.where()

if __name__ == "__main__":
    print(toml_data)
