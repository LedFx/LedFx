import sentry_sdk
from sentry_sdk.integrations.aiohttp import AioHttpIntegration

from ledfx.consts import DEV, PROJECT_VERSION

# Place your key between the quotes if you have a sentry.io account and wish to use it.
# Otherwise the LedFx sentry key is inserted here during deployment.

sentry_dsn = "DSN"
if (
    sentry_dsn
    == "https://691086dc41fa4218860be6ed4c888145@o482797.ingest.sentry.io/5533553"
):
    sentry_sdk.init(
        sentry_dsn,
        traces_sample_rate=1,
        integrations=[AioHttpIntegration()],
        release=f"ledfx@{PROJECT_VERSION}",
    )
elif DEV > 0:

    sentry_dsn = "https://de9ea3e00f334954b2f1478b90936d55@o482797.ingest.sentry.io/5886499"

    from subprocess import PIPE, Popen

    process = Popen(["git", "rev-parse", "HEAD"], stdout=PIPE)
    (commit_hash, err) = process.communicate()
    commit_hash = commit_hash[:7].decode("utf-8")
    exit_code = process.wait()

    sentry_sdk.init(
        sentry_dsn,
        traces_sample_rate=1,
        integrations=[AioHttpIntegration()],
        release=f"ledfx@{PROJECT_VERSION}-{commit_hash}",
    )
