"""Minimal STUN server (RFC 5389 Binding only) for the HA-Phone app.

The app learns its own address as the PBX sees it and puts that into its SDP. Without
it a phone behind NAT (guest WLAN, other subnet, emulator) advertises its private
address, Asterisk sends the door camera's early-media video there and the preview
stays black: the app sends no RTP before answering, so rtp_symmetric has nothing to
learn from. The provisioning config has always announced stun:<lan>:3478.
"""
import asyncio
import logging
import os
import socket
import struct

_log = logging.getLogger(__name__)

MAGIC_COOKIE = 0x2112A442
BINDING_REQUEST = 0x0001
BINDING_SUCCESS = 0x0101
ATTR_MAPPED_ADDRESS = 0x0001
ATTR_XOR_MAPPED_ADDRESS = 0x0020
_HEADER = struct.Struct("!HHI12s")


def stun_port_from_env() -> int:
    try:
        return int(os.environ.get("BPX_STUN_PORT", "3478"))
    except ValueError:
        return 3478


def _address_attr(attr_type: int, family: int, port: int, packed_ip: bytes) -> bytes:
    value = struct.pack("!BBH", 0, family, port) + packed_ip
    return struct.pack("!HH", attr_type, len(value)) + value


def binding_response(request: bytes, addr: tuple) -> bytes | None:
    """Success response for a Binding request from `addr`, None for anything else."""
    if len(request) < _HEADER.size:
        return None
    msg_type, length, cookie, txn = _HEADER.unpack_from(request)
    if msg_type != BINDING_REQUEST or msg_type & 0xC000 or len(request) < _HEADER.size + length:
        return None
    host, port = addr[0], addr[1]
    if ":" in host:
        family, packed = 0x02, socket.inet_pton(socket.AF_INET6, host)
        xor_key = struct.pack("!I", MAGIC_COOKIE) + txn
    else:
        family, packed = 0x01, socket.inet_aton(host)
        xor_key = struct.pack("!I", MAGIC_COOKIE)
    xor_ip = bytes(b ^ k for b, k in zip(packed, xor_key))
    attrs = _address_attr(ATTR_XOR_MAPPED_ADDRESS, family, port ^ (MAGIC_COOKIE >> 16), xor_ip)
    if cookie != MAGIC_COOKIE:
        # RFC 3489 clients (no magic cookie) only understand MAPPED-ADDRESS.
        attrs = _address_attr(ATTR_MAPPED_ADDRESS, family, port, packed)
    elif family == 0x01:
        attrs += _address_attr(ATTR_MAPPED_ADDRESS, family, port, packed)
    return _HEADER.pack(BINDING_SUCCESS, len(attrs), cookie, txn) + attrs


class _StunProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        response = binding_response(data, addr)
        if response is not None:
            self.transport.sendto(response, addr)


class StunServer:
    def __init__(self, port: int = 3478, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self._transport = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(_StunProtocol, local_addr=(self.host, self.port))
        self.port = self._transport.get_extra_info("sockname")[1]
        _log.info("STUN server listening on %s:%s/udp", self.host, self.port)

    async def stop(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None
