"""macOS main-thread compatibility for pystray's Darwin backend."""

import threading

import Foundation
import objc
import pystray


class _MainThreadCall(Foundation.NSObject):
    """Carry a synchronous callback request to the Cocoa main thread."""

    def initWithCallback_(self, callback):
        call = objc.super(_MainThreadCall, self).init()
        call.callback = callback
        call.event = threading.Event()
        call.result = None
        call.error = None
        return call


class _MainThreadDispatcher(Foundation.NSObject):
    """Expose the selector used to run callbacks on the main thread."""

    def runCall_(self, call):
        try:
            call.result = call.callback()
        except BaseException as error:  # noqa: BLE001
            call.error = error
        finally:
            call.event.set()


def _dispatch_to_main_thread(dispatcher, callback):
    """Run a callback on Cocoa's main thread and return its result."""

    if threading.current_thread() is threading.main_thread():
        return callback()

    call = _MainThreadCall.alloc().initWithCallback_(callback)
    dispatcher.performSelectorOnMainThread_withObject_waitUntilDone_(
        "runCall:", call, False
    )
    call.event.wait()
    if call.error:
        raise call.error
    return call.result


class Icon(pystray.Icon):
    """Dispatch AppKit-mutating pystray operations to the main thread."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._main_thread_dispatcher = _MainThreadDispatcher.alloc().init()

    def _dispatch(self, callback):
        """Synchronously dispatch a pystray backend operation."""

        return _dispatch_to_main_thread(self._main_thread_dispatcher, callback)

    def _show(self):
        """Show the tray icon on the Cocoa main thread."""

        return self._dispatch(super()._show)

    def _hide(self):
        """Hide the tray icon on the Cocoa main thread."""

        return self._dispatch(super()._hide)

    def _update_icon(self):
        """Update the tray image on the Cocoa main thread."""

        return self._dispatch(super()._update_icon)

    def _update_title(self):
        """Update the tray title on the Cocoa main thread."""

        return self._dispatch(super()._update_title)

    def _update_menu(self):
        """Update the tray menu on the Cocoa main thread."""

        return self._dispatch(super()._update_menu)

    def _stop(self):
        """Stop the tray event loop on the Cocoa main thread."""

        return self._dispatch(super()._stop)
