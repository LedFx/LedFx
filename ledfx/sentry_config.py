import sentry_sdk
from sentry_sdk.integrations.aiohttp import AioHttpIntegration

from ledfx.consts import PROJECT_VERSION

# This key is overwritten with our organizational sentry key as part of the deployment process.
# You're welcome to plug your own sentry key in if you're forking/doing development - sentry.io
# This current key is disabled and no data will be sent to anyone if you use this sentry key.

sentry_dsn = (
    "https://f2c38998265e4a9b8fa46356d4461237@o482797.ingest.sentry.io/5533553"
)

sentry_sdk.init(
    sentry_dsn,
    traces_sample_rate=1,
    integrations=[AioHttpIntegration()],
    release=f"ledfx@{PROJECT_VERSION}",
)
