import ledfx_assets

# TODO: Bump pyproject.toml if you bump this!
PROJECT_VERSION = "2.0.92"
PROJECT_NAME = "LedFx"
PROJECT_AUTHOR = "LedFx Developers"
PROJECT_LICENSE = "GPL-3.0"
CONFIG_MAJOR_VERSION = 2
CONFIG_MINOR_VERSION = 3
CONFIG_MICRO_VERSION = 0

# Dev turns sentry logging on and off
DEV = 0

CONFIGURATION_VERSION = "{}.{}.{}".format(
    CONFIG_MAJOR_VERSION, CONFIG_MINOR_VERSION, CONFIG_MICRO_VERSION
)
LEDFX_ASSETS_PATH = ledfx_assets.where()

if __name__ == "__main__":
    print(PROJECT_VERSION)
