import logging
import os
import sys

import sentry_sdk
from dotenv import load_dotenv
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from contextlib import contextmanager

from ledfx.consts import PROJECT_VERSION
from ledfx.utils import currently_frozen

_LOGGER = logging.getLogger(__name__)


@contextmanager
def suppress_sentry_breadcrumb():
    """
    Context manager to suppress a breadcrumb from being sent to Sentry.
    Use this to suppress a breadcrumb that is not relevant to the current
    context, e.g. a HTTP request for driving specific devices
    which otherwise spam a breadcrumb towards sentry at FPS rate!

    example in the function where the http request is made:

    with suppress_sentry_breadcrumb():
        your http sending code here
    """

    # Set a flag in the current scope
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag('suppress_breadcrumb', True)
        yield
        scope.remove_tag('suppress_breadcrumb')


def before_breadcrumb(crumb, hint):
    """
    Sentry callback to filter breadcrumbs.
    Use this to suppress a breadcrumb that is not relevant to the current
    Existing plumbing is against the suppress_breadcrumb tag
    Can be extended for specific logic or additional tags as required
    """

    # Check if the breadcrumb should be suppressed
    if crumb['category'] == 'http' and sentry_sdk.get_current_scope().tags.get('suppress_breadcrumb'):
        return None  # Skip this breadcrumb

    return crumb


# Load the prod.env - this does not exist by default, and will thus be false when run from source
extDataDir = os.path.dirname(os.path.realpath(__file__))

if currently_frozen():
    extDataDir = sys._MEIPASS
    load_dotenv(dotenv_path=os.path.join(extDataDir, "prod.env"))
else:
    parent_dir = os.path.dirname(extDataDir)
    load_dotenv(dotenv_path=os.path.join(parent_dir, "prod.env"))


is_release = os.getenv("IS_RELEASE", "false").lower()

if is_release == "false":
    _LOGGER.debug("Running in development mode.")
    sentry_dsn = "https://b192934eebd517c86bf7e9c512b3888a@o482797.ingest.sentry.io/4506350241841152"
    sample_rate = 1

    try:
        from subprocess import PIPE, Popen

        process = Popen(["git", "rev-parse", "HEAD"], stdout=PIPE)
        (commit_hash, err) = process.communicate()
        commit_hash = commit_hash[:7].decode("utf-8")
        exit_code = process.wait()
    # TODO: trap explicit exceptions if it becomes clear what they are
    except Exception as e:
        commit_hash = "unknown"
        _LOGGER.warning(f"Failed to get git commit hash: {e}")
    release = f"ledfx@{PROJECT_VERSION}-{commit_hash}"
else:
    _LOGGER.debug("Running in production mode.")
    # production / release behaviour due to injection of "prod" or anything really into ENVIRONMENT env variable
    sentry_dsn = "https://dc6070345a8dfa1f2f24433d16f7a133@o482797.ingest.sentry.io/4506350233321472"
    sample_rate = 0
    release = f"ledfx@{PROJECT_VERSION}"

_LOGGER.info("Sentry Configuration:")
_LOGGER.info(f"DSN (first ten): {sentry_dsn[8:18]}")
_LOGGER.info(f"Sample rate: {sample_rate}")
_LOGGER.info(f"LedFx release: {release}")

sentry_sdk.init(
    sentry_dsn,
    traces_sample_rate=sample_rate,
    integrations=[AioHttpIntegration()],
    release=release,
    before_breadcrumb=before_breadcrumb,
)
