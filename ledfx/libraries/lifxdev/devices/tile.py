#!/usr/bin/env python3

from __future__ import annotations

from ledfx.libraries.lifxdev.colors import color
from ledfx.libraries.lifxdev.devices import light
from ledfx.libraries.lifxdev.messages import packet, tile_messages

TILE_WIDTH = 8


class LifxTile(light.LifxLight):
    """Tile device control"""

    def __init__(self, *args, length: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._num_tiles: int | None = length

    def get_chain(self) -> packet.LifxResponse:
        """Get information about the current tile chain"""
        response = self.send_recv(
            tile_messages.GetDeviceChain(), res_required=True
        )
        assert response is not None
        response = response.pop()
        self._num_tiles = response.payload["total_count"]
        return response

    def get_num_tiles(self) -> int:
        """Get the number of tiles that can be controlled"""
        if self._num_tiles:
            return self._num_tiles
        else:
            return self.get_chain().payload["total_count"]

    def get_tile_colors(
        self, tile_index: int, *, length: int = 1
    ) -> list[list[color.Hsbk]]:
        """Get the color state for individual tiles.

        Args:
            tile_index: (int) The tile index in the chain to query.
            length: (int) The number of tiles to query.

        Returns:
            List of tile states.
        """
        get_request = tile_messages.GetTileState64(width=TILE_WIDTH)
        get_request["tile_index"] = tile_index
        get_request["length"] = length
        responses = self.send_recv(
            get_request, res_required=True, retry_recv=length > 1
        )
        assert responses is not None
        matrix_list: list[list[color.Hsbk]] = []
        for state in responses:
            matrix_list.append(
                [
                    color.Hsbk.from_packet(hsbk)
                    for hsbk in state.payload["colors"]
                ]
            )
        return matrix_list

    def set_tile_colors(
        self,
        tile_index: int,
        tile_colors: list[color.Hsbk],
        *,
        duration: float = 0.0,
        length: int = 1,
        ack_required: bool = False,
    ) -> packet.LifxResponse | None:
        """Set the tile colors

        Args:
            tile_index: (int) The tile index in the chain to query.
            tile_colors: List of colors to set the tile(s) to.
            duration: (float) The time in seconds to make the color transition.
            length: (int) The number of tiles to query.
            ack_required: (bool) True gets an acknowledgement from the device.
        """
        set_request = tile_messages.SetTileState64(width=TILE_WIDTH)
        set_request["tile_index"] = tile_index
        set_request["length"] = length
        set_request["duration"] = int(duration * 1000)
        set_request["colors"] = [
            hsbk_tuple.max_brightness(self.max_brightness).to_packet()
            for hsbk_tuple in map(color.Hsbk.from_tuple, tile_colors)
        ]
        return self.send_msg(set_request, ack_required=ack_required)
