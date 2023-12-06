import logging

from ledfx.consts import DEV, PROJECT_VERSION

_LOGGER = logging.getLogger(__name__)

# overall logic

# default is no sentry dsn
# sentry_dsn can be overridden by build scripts or a developer
# if a dev sets DEV to 1 or higher in const.py, sentry is turned on
# if they have overridden dsn it is used, else we put in a dev dsn

# Place your key between the quotes if you have a sentry.io account and wish to use it.

# the following is modified by some build scripts during release process
sentry_dsn = "DSN"
sample_rate = 0
release = f"ledfx@{PROJECT_VERSION}"

# a developer can decide to turn on sentry tracking to a specific backend,
# along with transaction measurements if they wish to by bumping up DEV value in
# consts.py to 1 or higher
if DEV > 0:
    # if a developer has overridden dsn, use it, else inject a dev dsn
    if len(sentry_dsn) == 3:  # avoid string replace problems with existing scripts
        sentry_dsn = "https://b192934eebd517c86bf7e9c512b3888a@o482797.ingest.sentry.io/4506350241841152"
    sample_rate = 1

    from subprocess import PIPE, Popen

    process = Popen(["git", "rev-parse", "HEAD"], stdout=PIPE)
    (commit_hash, err) = process.communicate()
    commit_hash = commit_hash[:7].decode("utf-8")
    exit_code = process.wait()
    release = f"ledfx@{PROJECT_VERSION}-{commit_hash}"


if sentry_dsn != "DSN":
    import sentry_sdk
    from sentry_sdk.integrations.aiohttp import AioHttpIntegration

    _LOGGER.info(
        f"Sentry config\ndsn first ten: {sentry_dsn[8:18]}\nsample_rate: {sample_rate}\nrelease: {release}"
    )
    sentry_sdk.init(
        sentry_dsn,
        traces_sample_rate=sample_rate,
        integrations=[AioHttpIntegration()],
        release=release,
    )
else:
    _LOGGER.info("Sentry not configured")
