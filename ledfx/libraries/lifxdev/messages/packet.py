#!/usr/bin/env python3

from __future__ import annotations

import collections
import dataclasses
import enum
import logging
import os
import re
import selectors
import socket
import struct
import sys
from collections.abc import Callable
from typing import Any, cast

BUFFER_SIZE = 65535
LIFX_PORT = 56700
TIMEOUT_S = 1


class NoResponsesError(Exception):
    pass


class LifxType(enum.Enum):
    """Type definition:

    0: (int) size in bits
    1: (char) struct format (None if size % 8 > 0)
    """

    bool = (1, None)
    char = (8, "c")
    f32 = (32, "f")
    s16 = (16, "h")
    u2 = (2, None)  # 8 bit int where only 2 bits are used
    u6 = (6, None)  # 8 bit int where only 6 bits are used
    u8 = (8, "B")
    u12 = (12, None)  # 16 bit int where only 12 bits are used
    u16 = (16, "H")
    u32 = (32, "I")
    u64 = (64, "Q")


class LifxStruct:
    """Packed structure for generating byte representations of LIFX bit tables.

    LIFX packets are little endian.

    Register definition:
        0: (str) name
        1: (enum) type, if a LifxStruct subclass, use the type instead of a str
        2: (int) number of items of the type
    """

    registers: list[tuple[str, LifxType | LifxStruct, int]] = []

    def __init__(self, **kwargs):
        # Set to tuples because they're immutable. _names and _sizes should not be changed.
        self._names: tuple[str, ...] = tuple(
            [rr[0].lower() for rr in self.registers]
        )
        for kw in kwargs:
            if kw not in self._names:
                name = type(self).__name__
                if hasattr(self, "name"):
                    name = getattr(self, "name")
                raise ValueError(f"Invalid keyword arg for {name}: {kw}")

        self._types = collections.OrderedDict()
        self._sizes = collections.OrderedDict()
        self._lens = collections.OrderedDict()
        self._values = collections.OrderedDict()
        for name, rr in zip(self._names, self.registers):
            self._types[name] = rr[1]
            self._sizes[name] = rr[1].value[0] * rr[2]
            self._lens[name] = rr[2]
            if isinstance(self._types[name], LifxType):
                default = [0] * self._lens[name]
            else:
                default = [self._types[name]] * self._lens[name]
            self._values[name] = default
            self.set_value(name, kwargs.get(name, default))

    def __str__(self) -> str:
        segments = [f"{nn}={self.get_value(nn)!r}" for nn in self._names]
        join = "\n".join(segments)
        return f"{join}"

    def __repr__(self) -> str:
        return f"<{type(self).__name__}({id(self)})>\n{self.__str__()}"

    def __eq__(self, other: LifxStruct) -> bool:
        if type(self) != type(other):  # noqa: E721
            return False

        for name in self._names:
            value_self = self.get_value(name)
            value_other = other.get_value(name)
            if value_self != value_other:
                return False
        return True

    @classmethod
    def from_bytes(cls, message_bytes: bytes) -> LifxStruct:
        """Create a LifxStruct from bytes

        Anything with irregular bits will have this class overrwitten.
        """
        decoded_registers = collections.defaultdict(list)

        offset = 0
        for reg_info in cls.registers:
            t_nbytes = 0
            rname, rtype, rlen = reg_info

            # Easy decoding using struct.unpack for LifxType data
            if isinstance(rtype, LifxType):
                if rtype.value[1] is None:
                    raise RuntimeError(
                        f"Register {rname} cannot be represented as bytes."
                    )

                t_nbytes = rtype.value[0] // 8 * rlen
                msg_chunk = message_bytes[offset : offset + t_nbytes]
                value_list = list(
                    struct.unpack("<" + rtype.value[1] * rlen, msg_chunk)
                )
                decoded_registers[rname] = value_list

            # If bytes are supposed to represent a type, use the from_bytes from that type
            else:
                t_nbytes = len(rtype) * rlen
                msg_chunk = message_bytes[offset : offset + t_nbytes]
                for _ in range(rlen):
                    decoded_registers[rname].append(
                        rtype.from_bytes(msg_chunk[: len(rtype)])
                    )
                    msg_chunk = msg_chunk[len(rtype) :]

            offset += t_nbytes

        return cls(**decoded_registers)

    def get_size_bits(self) -> int:
        """Get the size in bits of an individual LifxStruct object"""
        return sum(self._sizes.values())

    def get_size_bytes(self) -> int:
        """Return the number of bytes in the LifxStruct"""
        return self.get_size_bits() // 8

    def get_array_size(self, name: str) -> int:
        name = name.lower()
        return self._lens[name]

    def get_nbits_per_name(self, name: str) -> int:
        name = name.lower()
        return self._sizes[name]

    def get_nbytes_per_name(self, name: str) -> int:
        return self.get_nbits_per_name(name) // 8

    def get_type(self, name: str) -> LifxType | LifxStruct:
        name = name.lower()
        return self._types[name]

    @staticmethod
    def get_nbits_and_signed(
        register_type: LifxType | LifxStruct,
    ) -> tuple[int, bool]:
        """Get the number of bits used to represent positive numbers for a type"""
        n_bits = register_type.value[0]
        # struct identifiers are lowercase for signed types
        rtype_value: str | None = register_type.value[1]
        signed = rtype_value == rtype_value.lower() if rtype_value else False
        # if signed int, one of the bits is for determining the signed.
        if signed:
            n_bits -= 1
        return n_bits, signed

    def get_max(self, name: str) -> float:
        """Get the maximum value a member of an integer register can hold"""
        register_type = self.get_type(name)
        if register_type.value[1] is None:
            raise NotImplementedError(
                f"Maximum undefined for type: {register_type}"
            )

        # Floating point maximum
        if register_type.value[1] == "f":
            return sys.float_info.max

        n_bits, _ = self.get_nbits_and_signed(register_type)
        return (1 << n_bits) - 1

    def get_min(self, name: str) -> float:
        """Get the minimum value a member of an integer register can hold"""
        register_type = self.get_type(name)
        if register_type.value[1] is None:
            raise NotImplementedError(
                f"Maximum undefined for type: {register_type}"
            )

        # Floating point minimum
        if register_type.value[1] == "f":
            return -sys.float_info.max

        n_bits, signed = self.get_nbits_and_signed(register_type)
        if signed:
            return -1 << n_bits
        else:
            return 0

    @property
    def value(self) -> tuple[int, None]:
        """Mimic the value attribute of the LifxType enum"""
        return (self.get_size_bits(), None)

    def __len__(self) -> int:
        return self.len()

    def len(self) -> int:
        """Return the number of bytes in the LifxStruct"""
        return self.get_size_bytes()

    def __getitem__(self, name: str) -> Any:
        return self.get_value(name)

    def get_value(self, name: str) -> Any:
        """Get a register value by name.

        Returns:
            A single value if the register length is 1 else return the array of values.
        """
        name = name.lower()
        if name not in self._names:
            raise KeyError(f"{name!r} not a valid register name")

        register_type = self.get_type(name)
        value = self._values[name]
        if register_type.value[1] == "c":
            value = bytes(value).decode()
            # strip null bytes
            idx = value.find(chr(0))
            if idx >= 0:
                value = value[:idx]
        elif len(value) == 1:
            value = value[0]
        return value

    def _check_value(self, value: Any, name: str) -> Any:
        """Validate integer values are within bounds"""
        # Only integer/floating values can be checked.
        register_type = self.get_type(name)
        if not register_type.value[1] or register_type.value[1] == "c":
            return value

        min_value = self.get_min(name)
        max_value = self.get_max(name)
        if value < min_value or value > max_value:
            raise ValueError(
                f"value {value} out of bounds for register {name!r}"
            )
        return value

    def __setitem__(self, name: str, value: Any) -> None:
        self.set_value(name, value)

    def set_value(self, name: str, value: Any, idx: int | None = None) -> None:
        """Set a register value by name.

        Args:
            name: (str) name of the register to write
            value: Either a singular value or a list of values to write.
            idx: (int) if a single array item, the position in the array.
        """
        name = name.lower()
        if name not in self._names:
            raise KeyError(f"{name!r} not a valid register name")

        # Force reserved registers to be null
        if "reserved" in name:
            value = [0] * self.get_array_size(name)
            idx = None

        # Convert strings to bytes and pad them with zeros at the end of they are short
        n_items = self._lens[name]
        if isinstance(value, (bytes, str)):
            if isinstance(value, str):
                value = value.encode()
            if len(value) < n_items:
                margin = n_items - len(value)
                value += bytes(margin * [0])

        # Store char values as bytes always
        register_type = self._types[name]
        if register_type.value[1] == "c" and isinstance(value, (list, tuple)):
            if all([isinstance(vv, bytes) for vv in value]):
                value = b"".join(value)
            elif all([isinstance(vv, int) for vv in value]):
                value = bytes(value)

        # Validate that if a list was passed, that it matches the register length
        if isinstance(value, (bytes, list, str, tuple)):
            if len(value) != n_items:
                raise ValueError(
                    f"Value has length {len(value)}, "
                    f"but register {name} requires length {n_items}"
                )

        # Force the index to zero if a singular value has been passed in
        elif n_items == 1:
            idx = 0
        elif idx is None:
            raise ValueError("idx cannot be none for a singular value")

        # Set the value to the internal values dict
        if isinstance(value, (bytes, str)):
            self._values[name] = value
        elif isinstance(value, (list, tuple)):
            self._values[name] = [self._check_value(vv, name) for vv in value]
        else:
            self._values[name][idx] = self._check_value(value, name)

    def to_bytes(self) -> bytes:
        """Convert the LifxStruct to its bytes representation

        Args:
            as_ints: (bool) Return the list of ints representing the bytes.
        """
        assert len(self._names) == len(self._values)
        assert len(self._types) == len(self._values)
        assert len(self._sizes) == len(self._values)
        assert len(self._lens) == len(self._values)

        message_bytes = b""
        for reg_info in self.registers:
            rname, rtype, rlen = reg_info

            # Use struct.path for LifxTypes
            if isinstance(rtype, LifxType):
                if rtype.value[1] is None:
                    raise RuntimeError(
                        f"Register {rname} cannot be represented as bytes."
                    )
                fmt = "<" + rtype.value[1] * rlen
                values = self._values[rname]
                # Convert bytes  to list for struct packing
                if isinstance(values, bytes):
                    values = [bytes([vv]) for vv in values]
                message_bytes += struct.pack(fmt, *values)

            # Use the LifxStruct to_bytes when not a LifxType
            else:
                for lstruct in self._values[rname]:
                    message_bytes += lstruct.to_bytes()

        return message_bytes


REGISTER_T = list[tuple[str, LifxType, int]]


# Header description: https://lan.developer.lifx.com/docs/header-description


class Frame(LifxStruct):
    registers: REGISTER_T = [
        ("size", LifxType.u16, 1),
        ("protocol", LifxType.u12, 1),
        ("addressable", LifxType.bool, 1),
        ("tagged", LifxType.bool, 1),
        ("origin", LifxType.u2, 1),
        ("source", LifxType.u32, 1),
    ]

    def set_value(self, name: str, value: int) -> None:
        """LIFX Frame specification requires certain fields to be constant."""
        if name.lower() == "protocol":
            value = 1024
        elif name.lower() == "addressable":
            value = True
        elif name.lower() == "origin":
            value = 0
        super().set_value(name, value)

    def to_bytes(self) -> bytes:
        """Override defaults because of sub-byte packing"""
        size = self.get_value("size")
        source = self.get_value("source")

        bit_field = self.get_value("protocol")
        offset = self.get_nbits_per_name("protocol")
        bit_field |= self.get_value("addressable") << offset
        offset += self.get_nbits_per_name("addressable")
        bit_field |= self.get_value("tagged") << offset
        offset += self.get_nbits_per_name("tagged")
        bit_field |= self.get_value("origin") << offset

        return struct.pack("<HHI", size, bit_field, source)

    @classmethod
    def from_bytes(cls, message_bytes: bytes) -> Frame:
        """Override defaults because of sub-byte packing"""
        size, bit_field, source = struct.unpack("<HHI", message_bytes)
        frame = cls(size=size, source=source)

        shift = frame.get_nbits_per_name("protocol")
        frame["protocol"] = bit_field % (1 << shift)
        bit_field = bit_field >> shift

        shift = frame.get_nbits_per_name("addressable")
        frame["addressable"] = bool(bit_field % (1 << shift))
        bit_field = bit_field >> shift

        shift = frame.get_nbits_per_name("tagged")
        frame["tagged"] = bool(bit_field % (1 << shift))
        bit_field = bit_field >> shift

        frame["origin"] = bit_field
        return frame


class FrameAddress(LifxStruct):
    registers: REGISTER_T = [
        ("target", LifxType.u8, 8),
        ("reserved_1", LifxType.u8, 6),
        ("res_required", LifxType.bool, 1),
        ("ack_required", LifxType.bool, 1),
        ("reserved_2", LifxType.u6, 1),
        ("sequence", LifxType.u8, 1),
    ]

    def set_value(self, name: str, value: int | str | list[int]) -> None:
        """LIFX Frame Address specification requires certain fields to be constant.

        This also allows for the proper parsing of mac addresses.
        """
        name = name.lower()
        if name == "target":
            if isinstance(value, str):
                if is_str_mac(value):
                    value = mac_str_to_int_list(value)

        super().set_value(name, value)

    def _fmt(self, name: str) -> str:
        """Create a format string for a register name"""
        type_value = self.get_type(name).value[1]
        assert type_value
        return "<" + type_value * self.get_array_size(name)

    def to_bytes(self) -> bytes:
        """Override defaults because of sub-byte packing"""

        target_bytes = struct.pack(
            self._fmt("target"), *self.get_value("target")
        )
        res_1_bytes = struct.pack(
            self._fmt("reserved_1"), *self.get_value("reserved_1")
        )
        sequence_bytes = struct.pack(
            self._fmt("sequence"), self.get_value("sequence")
        )

        bit_field = int(self.get_value("res_required"))
        offset = self.get_nbits_per_name("res_required")
        bit_field |= int(self.get_value("ack_required")) << offset
        bit_field_bytes = struct.pack("<B", bit_field)

        return target_bytes + res_1_bytes + bit_field_bytes + sequence_bytes

    @classmethod
    def from_bytes(cls, message_bytes: bytes) -> FrameAddress:
        """Override defaults because of sub-byte packing"""
        frame_address = cls()
        get_len = frame_address.get_nbytes_per_name
        get_nbits = frame_address.get_nbits_per_name

        chunk_len = get_len("target")
        target_bytes = message_bytes[:chunk_len]
        offset = chunk_len + get_len("reserved_1")
        chunk_len = (
            get_nbits("res_required")
            + get_nbits("ack_required")
            + get_nbits("reserved_2")
        )
        chunk_len //= 8
        bit_field_bytes = message_bytes[offset : offset + chunk_len]
        offset += chunk_len

        chunk_len = get_len("sequence")
        sequence_bytes = message_bytes[offset : offset + chunk_len]

        frame_address["target"] = list(
            struct.unpack(frame_address._fmt("target"), target_bytes)
        )
        frame_address["sequence"] = list(
            struct.unpack(frame_address._fmt("sequence"), sequence_bytes)
        )
        (bit_field,) = struct.unpack("<B", bit_field_bytes)
        frame_address["res_required"] = bool(bit_field % 2)
        frame_address["ack_required"] = bool(bit_field // 2)

        return frame_address


class ProtocolHeader(LifxStruct):
    registers: REGISTER_T = [
        ("reserved_1", LifxType.u64, 1),
        ("type", LifxType.u16, 1),
        ("reserved_2", LifxType.u16, 1),
    ]


class Hsbk(LifxStruct):
    registers: REGISTER_T = [
        ("hue", LifxType.u16, 1),
        ("saturation", LifxType.u16, 1),
        ("brightness", LifxType.u16, 1),
        ("kelvin", LifxType.u16, 1),
    ]

    def set_value(self, name: str, value: int | list[int]):
        """Kelvin must be between 2500 and 9000."""
        if isinstance(value, list):
            if len(value) > 1:
                raise ValueError("HSBK value as list must be length 1")
            hsbk_value = value[0]
        else:
            hsbk_value = value

        # Only value check when setting a non-zero value.
        # Value checking on the zero would break the default constructor.
        if name.lower() == "kelvin" and hsbk_value:
            if hsbk_value < 2500 or hsbk_value > 9000:
                raise ValueError("Kelvin out of range.")

        super().set_value(name, hsbk_value)


#
# Handle payload messages and responses
#


class LifxMessage(LifxStruct):
    """LIFX struct used as a message type payload."""

    # integer identifier of for the protocol header of LIFX packets.
    name: str
    type: str

    def __repr__(self) -> str:
        super_str = super().__str__()
        msg_str = f"<{self.name}({self.type}): {id(self)}>"
        if super_str:
            msg_str = f"{msg_str}\n{super_str}"
        return msg_str

    def __str__(self) -> str:
        super_str = super().__str__()
        msg_str = f"<{self.name}({self.type})>"
        if super_str:
            msg_str = f"{msg_str}\n{super_str}"
        return msg_str

    @classmethod
    def from_bytes(cls, message_bytes: bytes) -> LifxMessage:
        return cast(cls, super().from_bytes(message_bytes))


@dataclasses.dataclass
class LifxResponse:
    addr: tuple[str, int]
    frame: Frame
    frame_address: FrameAddress
    protocol_header: ProtocolHeader
    payload: LifxMessage

    def __str__(self) -> str:
        return "\n".join(
            [
                f"IP: {self.addr[0]}:{self.addr[1]}",
                "---",
                "LifxResponse.frame:",
                str(self.frame),
                "---",
                "LifxResponse.frame_address:",
                str(self.frame_address),
                "---",
                "LifxResponse.protocol_header:",
                str(self.protocol_header),
                "---",
                str(self.payload),
            ]
        )


# Used for parsing responses from LIFX bulbs
# This maps the protocol header type to a LifxMessage class to generate using bytes
_MESSAGE_TYPES: dict[int, type[LifxMessage]] = {}


def set_message_type(message_type: int) -> Callable:
    """Create a LifxMessage class with the message type auto-set.

    Args:
        message_type: (int) LIFX message type for the protocol header
    """

    def _msg_type_decorator(cls) -> type:
        class _LifxMessage(cls):
            pass

        _LifxMessage.name = cls.__name__
        _LifxMessage.type = message_type
        _MESSAGE_TYPES[message_type] = _LifxMessage
        return _LifxMessage

    return _msg_type_decorator


@set_message_type(45)
class Acknowledgement(LifxMessage):
    """Acknowledgement message

    Defined here: https://lan.developer.lifx.com/docs/device-messages
    This is the message type returned when ack_required=True in the frame address.
    """

    pass


#
# Socket communication
#


@dataclasses.dataclass
class UdpSender:
    """Send messages to a single IP/port"""

    # IP address of the LIFX device.
    ip: str

    # UDP socket for communication
    comm: socket.socket

    # UDP port on the LIFX device
    port: int = LIFX_PORT

    # Mac address of the LIFX device
    mac_addr: str | None = None

    # Buffer size for receiving UDP messages
    buffer_size: int = BUFFER_SIZE


class PacketComm:
    """Communicate packets with LIFX devices"""

    def __init__(
        self,
        comm: UdpSender,
        verbose: bool = False,
        timeout: float = TIMEOUT_S,
    ):
        """Create a packet communicator

        Args:
            comm: (socket) pre-configured UDP socket.
            verbose: (bool) If true, log to info instead of debug.
        """
        self._comm = comm
        self._comm.comm.setblocking(False)
        self._log_func = logging.info if verbose else logging.debug
        self._timeout = timeout

    @property
    def ip(self) -> str:
        return self._comm.ip

    @staticmethod
    def decode_bytes(
        message_bytes: bytes,
        message_addr: tuple[str, int],
        nominal_source: int | None = None,
        nominal_sequence: int | None = None,
    ) -> LifxResponse:
        def _get_nbytes(cls: type[LifxStruct]) -> int:
            n_bits = 0
            for _, rtype, rlen in cls.registers:
                n_bits += rtype.value[0] * rlen
            return n_bits // 8

        # Decode the Frame information
        chunk_len = _get_nbytes(Frame)
        frame = Frame.from_bytes(message_bytes[:chunk_len])

        # Verify the message size matches the expected size
        size = frame["size"]
        if len(message_bytes) != size:
            raise RuntimeError(
                f"Message size mismatch: R({len(message_bytes)}) != E({size})"
            )

        # Verify the source is the expected source
        if nominal_source is not None:
            source = frame["source"]
            if source != nominal_source:
                raise RuntimeError(
                    f"Source mismatch: R({source}) != E({nominal_source})"
                )

        # Decode the Frame Address
        offset = chunk_len
        chunk_len = _get_nbytes(FrameAddress)
        frame_address = FrameAddress.from_bytes(
            message_bytes[offset : offset + chunk_len]
        )

        # Verify the sequence is the expected sequence
        if nominal_sequence is not None:
            sequence = frame_address["sequence"]
            if sequence != nominal_sequence:
                raise RuntimeError(
                    f"Sequence mismatch: R({sequence}) != E({nominal_sequence})"
                )

        # Decode the payload
        offset += chunk_len
        chunk_len = _get_nbytes(ProtocolHeader)
        protocol_header = cast(
            ProtocolHeader,
            ProtocolHeader.from_bytes(
                message_bytes[offset : offset + chunk_len]
            ),
        )

        offset += chunk_len
        payload_klass = _MESSAGE_TYPES[protocol_header["type"]]
        chunk_len = _get_nbytes(payload_klass)
        payload = payload_klass.from_bytes(
            message_bytes[offset : offset + chunk_len]
        )

        return LifxResponse(
            addr=message_addr,
            frame=frame,
            frame_address=frame_address,
            protocol_header=protocol_header,
            payload=payload,
        )

    @staticmethod
    def get_bytes_and_source(
        *,
        payload: LifxMessage,
        mac_addr: str | int | None = None,
        res_required: bool = False,
        ack_required: bool = False,
        sequence: int = 0,
        source: int | None = None,
    ) -> tuple[bytes, int]:
        """Generate LIFX packet bytes.

        Args:
            payload: (LifxMessage) Payload to encode as bytes.
            mac_addr: (str) MAC address of the target bulb.
            res_required: (bool) Require a response from the light.
            ack_required: (bool) Require an acknowledgement from the light.
            sequence: (int) Optional identifier to label packets.
            source: (int) Optional unique identifier to

        Returns:
            bytes and source identifier
        """
        frame = Frame()
        frame_address = FrameAddress()
        protocol_header = ProtocolHeader()

        # Set the frame address fields
        if mac_addr:
            frame_address["target"] = mac_addr
        frame_address["res_required"] = res_required
        frame_address["ack_required"] = ack_required
        frame_address["sequence"] = sequence

        # Protocol header only requires setting the type.
        if not payload.type:
            raise ValueError("Payload has no message type.")
        protocol_header["type"] = payload.type

        # Generate the frame
        # tagged must be true when sending a GetService(2)
        frame["tagged"] = not sum(frame_address["target"]) or payload.type == 2
        frame["source"] = os.getpid() if source is None else source
        frame["size"] = (
            len(frame)
            + len(frame_address)
            + len(protocol_header)
            + len(payload)
        )

        # Generate the bytes for the packet
        packet_bytes = frame.to_bytes()
        packet_bytes += frame_address.to_bytes()
        packet_bytes += protocol_header.to_bytes()
        packet_bytes += payload.to_bytes()

        return packet_bytes, frame["source"]

    def send_recv(
        self,
        *,
        ip: str | None = None,
        port: int | None = None,
        mac_addr: str | None = None,
        comm: socket.socket | None = None,
        retry_recv: bool = False,
        verbose: bool = False,
        **kwargs,
    ) -> list[LifxResponse]:
        """Send a packet to a LIFX device or broadcast address and get responses

        Args:
            ip: (str) Override the IP address.
            port: (int) Override the UDP port.
            mac_addr: (str) Override the MAC address.
            comm: (socket) Override the UDP socket.
            retry_recv: (bool) Re-run recv_from until there are no more packets.
            verbose: (bool) Use logging.info for messages.
            kwargs: Keyword arguments for for get_bytes_and_source.

        Returns:
            If a response or acknowledgement requested, return them.
        """
        addr = (ip or self._comm.ip, port or self._comm.port)
        comm = comm or self._comm.comm
        payload_name = kwargs["payload"].name

        source = self.send(
            ip=ip,
            port=port,
            mac_addr=mac_addr,
            comm=comm,
            verbose=verbose,
            **kwargs,
        )
        kwargs.pop("source", None)

        responses = []
        if kwargs.get("ack_required", False) or kwargs.get(
            "res_required", False
        ):
            selector = selectors.DefaultSelector()
            selector.register(comm, selectors.EVENT_READ)
            while True:
                new_responses = self.recv(
                    comm=comm,
                    selector=selector,
                    source=source,
                    verbose=verbose,
                    **kwargs,
                )
                responses.extend(new_responses)
                if not (new_responses and retry_recv):
                    break

            if not responses:
                raise NoResponsesError(
                    f"Did not get a response from {addr[0]} with message: {payload_name}"
                )
        return responses

    def send(
        self,
        *,
        ip: str | None = None,
        port: int | None = None,
        mac_addr: str | None = None,
        comm: socket.socket | None = None,
        verbose: bool = False,
        **kwargs,
    ) -> int:
        """Send a packet to a LIFX device or broadcast address and get responses

        Args:
            ip: (str) Override the IP address.
            port: (int) Override the UDP port.
            mac_addr: (str) Override the MAC address.
            comm: (socket) Override the UDP socket.
            verbose: (bool) Use logging.info for messages.
            kwargs: Keyword arguments for for get_bytes_and_source.

        Returns:
            Source identifier of the packet for responses
        """
        log_func = logging.info if verbose else self._log_func
        addr = (ip or self._comm.ip, port or self._comm.port)
        comm = comm or self._comm.comm
        kwargs["mac_addr"] = mac_addr or self._comm.mac_addr

        packet_bytes, source = self.get_bytes_and_source(**kwargs)
        payload_name = kwargs["payload"].name
        log_func(f"Sending {payload_name} message to {addr[0]}:{addr[1]}")
        comm.sendto(packet_bytes, addr)
        return source

    def recv(
        self,
        *,
        comm: socket.socket | None = None,
        selector: selectors.BaseSelector | None = None,
        source: int | None = None,
        verbose: bool = False,
        **kwargs,
    ) -> list[LifxResponse]:
        log_func = logging.info if verbose else self._log_func
        comm = comm or self._comm.comm
        payload_name = kwargs["payload"].name

        if not selector:
            selector = selectors.DefaultSelector()
            selector.register(comm, selectors.EVENT_READ)
        responses = []
        events = selector.select(timeout=self._timeout)
        for key, event in events:
            assert event & selectors.EVENT_READ
            assert key.fileobj == self._comm.comm
            recv_bytes, recv_addr = comm.recvfrom(self._comm.buffer_size)
            response = self.decode_bytes(
                recv_bytes, recv_addr, source, kwargs.get("sequence", 0)
            )
            responses.append(response)
            payload_name = response.payload.name
            log_func(
                f"Received {payload_name} message from {recv_addr[0]}:{recv_addr[1]}"
            )

        return responses


def is_str_ipaddr(ipaddr: str) -> bool:
    """Check of a string is an IP address"""
    if re.match(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", ipaddr) is None:
        return False

    try:
        ip_nums = map(int, ipaddr.split("."))
        nums_valid = [0 <= n <= 255 for n in ip_nums]
    except ValueError:
        return False

    return all(nums_valid)


def is_str_mac(mac: str) -> bool:
    """Check if a string is a MAC address"""
    if re.match(r"(\S\S):" * 5 + r"(\S\S)", mac) is None:
        return False

    try:
        mac_nums = [int("0x" + ch, 16) for ch in mac.split(":")]
        nums_valid = [0 <= n <= 255 for n in mac_nums]
    except ValueError:
        return False

    return all(nums_valid)


def _mac_str_to_int(mac_str: str) -> int:
    # Swap endianness, then convert to an integer
    hex_str = "0x" + "".join(reversed(mac_str.split(":")))
    return int(hex_str, 16)


def mac_str_to_int_list(mac_str: str) -> list[int]:
    mac_int = _mac_str_to_int(mac_str)
    int_list: list[int] = []
    for _ in range(8):
        int_list.append(mac_int % (1 << 8))
        mac_int = mac_int >> 8
    return int_list
