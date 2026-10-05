"""Independent E1.31 wire oracle for native sender tests (literal offsets)."""


def decode_packet(packet: bytes | bytearray) -> dict[str, object]:
    """Validate PDU framing and decode fields without using production helpers."""
    if len(packet) < 49 or packet[:16] != bytes.fromhex(
        "001000004153432d45312e3137000000"
    ):
        raise ValueError("invalid E1.31 preamble or packet length")
    for offset in (16, 38):
        if int.from_bytes(packet[offset : offset + 2], "big") != 0x7000 | (
            len(packet) - offset
        ):
            raise ValueError("invalid root/framing length")
    root = int.from_bytes(packet[18:22], "big")
    vector = int.from_bytes(packet[40:44], "big")
    fields: dict[str, object] = {"cid": bytes(packet[22:38])}
    if (root, vector) == (4, 2):
        if len(packet) != 638 or packet[115:126] != bytes.fromhex(
            "720b02a100000001020100"
        ):
            raise ValueError("invalid data length or DMP header")
        fields.update(
            kind="data",
            sequence=packet[111],
            options=packet[112],
            universe=int.from_bytes(packet[113:115], "big"),
            payload=bytes(packet[126:]),
        )
    elif (root, vector) == (8, 1):
        if len(packet) != 49 or packet[47:49] != bytes(2):
            raise ValueError("invalid synchronization packet")
        fields.update(
            kind="sync",
            sequence=packet[44],
            universe=int.from_bytes(packet[45:47], "big"),
        )
    elif (root, vector) == (8, 2):
        if not 120 <= len(packet) <= 1144 or len(packet) % 2:
            raise ValueError("invalid discovery length")
        if packet[108:112] != bytes(4) or packet[114:118] != bytes.fromhex("00000001"):
            raise ValueError("invalid discovery header")
        if int.from_bytes(packet[112:114], "big") != 0x7000 | (len(packet) - 112):
            raise ValueError("invalid discovery PDU length")
        fields.update(
            kind="discovery",
            page=packet[118],
            last_page=packet[119],
            universes=tuple(
                int.from_bytes(packet[i : i + 2], "big")
                for i in range(120, len(packet), 2)
            ),
        )
    else:
        raise ValueError("unknown E1.31 vectors")
    return fields
