import asyncio
import logging

from ledfx.events import Event

_LOGGER = logging.getLogger(__name__)


class VisDeduplicateQ(asyncio.Queue):
    def __init__(self, maxsize=0):
        super().__init__(maxsize)

    def put_nowait(self, item):
        # Check if is a visualisation update message
        if (
            item.get("event_type") == Event.DEVICE_UPDATE
            or item.get("event_type") == Event.VISUALISATION_UPDATE
        ):
            # check if it is a duplicate and just return without queing if it is
            if any(
                self.is_similar(item, existing_item)
                for existing_item in self._queue
            ):
                # TODO: remove this logging
                _LOGGER.warning(
                    f"Queue: {hex(id(self))} discarding, qsize {self.qsize()}"
                )
                return
        super().put_nowait(item)

    def is_similar(self, new, queued):
        # We know we are already one of the correct types, but is it the same as queued
        # then check if it is for the same device
        if new.get("event_type") == queued.get("event_type") and new.get(
            "vis_id"
        ) == queued.get("vis_id"):
            return True
        return False
