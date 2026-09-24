"""STUN Binding server the app uses to put its NAT-mapped address into the SDP."""
import asyncio
import os
import socket
import struct

import pytest

from backend.stun_server import MAGIC_COOKIE, StunServer, binding_response

TXN = bytes(range(12))


def _request(cookie=MAGIC_COOKIE, msg_type=0x0001):
    return struct.pack("!HHI12s", msg_type, 0, cookie, TXN)


def _attrs(response):
    msg_type, length, cookie, txn = struct.unpack_from("!HHI12s", response)
    attrs, pos = {}, 20
    while pos < 20 + length:
        attr_type, attr_len = struct.unpack_from("!HH", response, pos)
        attrs[attr_type] = response[pos + 4:pos + 4 + attr_len]
        pos += 4 + attr_len
    return msg_type, cookie, txn, attrs


def test_binding_response_carries_xor_mapped_and_mapped_address():
    msg_type, cookie, txn, attrs = _attrs(binding_response(_request(), ("192.168.101.113", 40001)))
    assert (msg_type, cookie, txn) == (0x0101, MAGIC_COOKIE, TXN)
    _, family, xport = struct.unpack_from("!BBH", attrs[0x0020])
    xip = bytes(b ^ k for b, k in zip(attrs[0x0020][4:], struct.pack("!I", MAGIC_COOKIE)))
    assert family == 1 and xport ^ (MAGIC_COOKIE >> 16) == 40001 and socket.inet_ntoa(xip) == "192.168.101.113"
    _, _, port = struct.unpack_from("!BBH", attrs[0x0001])
    assert port == 40001 and socket.inet_ntoa(attrs[0x0001][4:]) == "192.168.101.113"


def test_classic_rfc3489_request_gets_plain_mapped_address():
    _, _, _, attrs = _attrs(binding_response(_request(cookie=0), ("10.0.0.5", 5000)))
    assert set(attrs) == {0x0001}


@pytest.mark.parametrize("data", [b"", b"\x00" * 10, _request(msg_type=0x0101), b"INVITE sip:x SIP/2.0\r\n" * 2])
def test_non_binding_datagrams_are_ignored(data):
    assert binding_response(data, ("10.0.0.5", 5000)) is None


@pytest.mark.asyncio
async def test_server_answers_over_udp():
    server = StunServer(port=0, host="127.0.0.1")
    await server.start()
    try:
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.bind(("127.0.0.1", 0))
        await loop.sock_sendto(sock, _request(), ("127.0.0.1", server.port))
        data = await asyncio.wait_for(loop.sock_recv(sock, 512), 2)
        _, _, _, attrs = _attrs(data)
        assert struct.unpack_from("!BBH", attrs[0x0001])[2] == sock.getsockname()[1]
        sock.close()
    finally:
        await server.stop()
