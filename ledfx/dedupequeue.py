import asyncio
import logging

from ledfx.events import Event

_LOGGER = logging.getLogger(__name__)


class VisDeduplicateQ(asyncio.Queue):
    """
    Deduplicate queue for visualisation updates

    Queues carrying visualisation updates to devices and virtual
    in the front end can lag hard if the front end is struggling.

    Although the backend forces a queue flush if the depth gets to 256
    any visualisation update in in the queue is just old data
    it is better not to queue an update if one is already in the queue
    rather than let 10s of old updates build up

    Uses private access to  _queue to check for duplicates
    """

    def __init__(self, maxsize=0):
        super().__init__(maxsize)

    def put_nowait(self, item):

        # to debug depth of queues and queue leakage enable teleplot below
        # from ledfx.utils import Teleplot
        # Teleplot.send(f"{hex(id(self))}:{self.qsize()}")

        # protect against None item flushing during socket closure
        if item:
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
                    _LOGGER.info(
                        f"Queue: {hex(id(self))} discarding, qsize {self.qsize()}"
                    )
                    return
        super().put_nowait(item)

    def is_similar(self, new, queued):
        # We know we are already one of the correct types, but is it the same as queued
        # then check if it is for the same device

        # Protect against None events
        if new is None or queued is None:
            return False

        if new.get("event_type") == queued.get("event_type") and new.get(
            "vis_id"
        ) == queued.get("vis_id"):
            return True

        return False
