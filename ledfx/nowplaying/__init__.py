import sys

NOW_PLAYING_AVAILABLE = False

if sys.platform == "win32":
    from ledfx.nowplaying.providers.windows_smtc import is_available

    NOW_PLAYING_AVAILABLE = is_available()
elif sys.platform == "linux":
    from ledfx.nowplaying.providers.linux_mpris import is_available

    NOW_PLAYING_AVAILABLE = is_available()
elif sys.platform == "darwin":
    from ledfx.nowplaying.providers.macos_stub import is_available

    NOW_PLAYING_AVAILABLE = is_available()
