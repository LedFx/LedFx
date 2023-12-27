# Couldn't get this to work. Will revisit.
# from packaging.version import Version
import tomli

# Read the pyproject.toml file
with open("../pyproject.toml", 'rb') as file:
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

CONFIGURATION_VERSION = "{}.{}.{}".format(
    CONFIG_MAJOR_VERSION, CONFIG_MINOR_VERSION, CONFIG_MICRO_VERSION
)

if __name__ == "__main__":
    print(toml_data)
