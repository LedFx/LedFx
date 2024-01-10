import logging
import os

import sentry_sdk
from sentry_sdk.integrations.aiohttp import AioHttpIntegration

from ledfx.consts import PROJECT_VERSION

_LOGGER = logging.getLogger(__name__)


is_release = os.getenv("IS_RELEASE", "false").lower()

if is_release == "false":
    sentry_dsn = "https://b192934eebd517c86bf7e9c512b3888a@o482797.ingest.sentry.io/4506350241841152"
    sample_rate = 1

    try:
        from subprocess import PIPE, Popen

        process = Popen(["git", "rev-parse", "HEAD"], stdout=PIPE)
        (commit_hash, err) = process.communicate()
        commit_hash = commit_hash[:7].decode("utf-8")
        exit_code = process.wait()
    except Exception as e:
        commit_hash = "unknown"
        _LOGGER.warning(f"Failed to get git commit hash: {e}")
    release = f"ledfx@{PROJECT_VERSION}-{commit_hash}"
else:
    # production / release behaviour due to injection of "prod" or anything really into ENVIRONMENT env variable
    sentry_dsn = "https://dc6070345a8dfa1f2f24433d16f7a133@o482797.ingest.sentry.io/4506350233321472"
    sample_rate = 0
    release = f"ledfx@{PROJECT_VERSION}"

_LOGGER.info(
    f"Sentry config\ndsn first ten: {sentry_dsn[8:18]}\nsample_rate: {sample_rate}\nrelease: {release}"
)
sentry_sdk.init(
    sentry_dsn,
    traces_sample_rate=sample_rate,
    integrations=[AioHttpIntegration()],
    release=release,
)
