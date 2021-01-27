# This file is overwritten with organisational sentry data as part of the deployment process.
# You're welcome to plug your own sentry keys in if you're forking/doing development.

import sentry_sdk
from sentry_sdk.integrations.aiohttp import AioHttpIntegration

from ledfx.consts import PROJECT_VERSION

sentry_sdk.init(
    "SENTRY-DSN",
    traces_sample_rate=1,
    integrations=[AioHttpIntegration()],
    release=f"ledfx@{PROJECT_VERSION}",
)
