"""Exercises the embedded LDAP phonebook server over a real TCP socket with
hand-encoded BER messages - the same wire format a Gigaset base sends for its
LDAP "Netzverzeichnis" lookups (anonymous bind, then one search per lookup)."""

import asyncio

import pytest
import pytest_asyncio

from backend.ldap_server import PhonebookLdapServer


# ── Tiny BER encoder (test-side client) ───────────────────────────────────────
def _ber_length(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def _tlv(tag: int, content: bytes) -> bytes:
    return bytes([tag]) + _ber_length(len(content)) + content


def _ber_int(value: int, tag: int = 0x02) -> bytes:
    body = value.to_bytes((value.bit_length() // 8) + 1, "big", signed=True) if value else b"\x00"
    return _tlv(tag, body)


def _ber_str(value: str, tag: int = 0x04) -> bytes:
    return _tlv(tag, value.encode())


def _bind_request(message_id: int, dn: str = "", password: str = "") -> bytes:
    op = _tlv(0x60, _ber_int(3) + _ber_str(dn) + _tlv(0x80, password.encode()))
    return _tlv(0x30, _ber_int(message_id) + op)


def _search_request(message_id: int, base: str, filter_bytes: bytes, size_limit: int = 0) -> bytes:
    op = _tlv(
        0x63,
        _ber_str(base)
        + _ber_int(2, tag=0x0A)  # scope wholeSubtree
        + _ber_int(0, tag=0x0A)  # derefAliases never
        + _ber_int(size_limit)
        + _ber_int(0)
        + _tlv(0x01, b"\x00")  # typesOnly FALSE
        + filter_bytes
        + _tlv(0x30, b""),  # attributes: all
    )
    return _tlv(0x30, _ber_int(message_id) + op)


def _filter_present(attr: str) -> bytes:
    return _tlv(0x87, attr.encode())


def _filter_substrings(attr: str, any_part: str) -> bytes:
    subs = _tlv(0x30, _tlv(0x81, any_part.encode()))  # [1] any
    return _tlv(0xA4, _ber_str(attr) + subs)


def _filter_or(*filters: bytes) -> bytes:
    return _tlv(0xA1, b"".join(filters))


# ── Minimal response decoding ─────────────────────────────────────────────────
def _read_tlv(data: bytes, offset: int):
    tag = data[offset]
    length = data[offset + 1]
    start = offset + 2
    if length & 0x80:
        n = length & 0x7F
        length = int.from_bytes(data[start : start + n], "big")
        start += n
    return tag, data[start : start + length], start + length


def _decode_messages(data: bytes) -> list[tuple[int, bytes]]:
    """Returns [(op_tag, op_content)] for every LDAPMessage in `data`."""
    messages = []
    offset = 0
    while offset < len(data):
        _tag, envelope, offset = _read_tlv(data, offset)
        _mid_tag, _mid, inner_next = _read_tlv(envelope, 0)
        op_tag, op_content, _ = _read_tlv(envelope, inner_next)
        messages.append((op_tag, op_content))
    return messages


def _entry_strings(op_content: bytes) -> str:
    return op_content.decode("utf-8", errors="replace")


async def _roundtrip(port: int, *requests: bytes) -> list[tuple[int, bytes]]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    for request in requests:
        writer.write(request)
    await writer.drain()
    writer.write_eof()
    data = await reader.read()
    writer.close()
    await writer.wait_closed()
    return _decode_messages(data)


@pytest_asyncio.fixture
async def ldap_server(client):
    """LDAP server on an ephemeral port, phonebook seeded via the API.

    The whole test run shares ONE SQLite DB (session-scoped tmp_data_dir),
    so leftover phonebook rows from other tests would break exact-count
    assertions - wipe the table first."""
    for entry in client.get("/api/phonebook").json():
        client.delete(f"/api/phonebook/{entry['id']}")
    created_ids = []
    for name, number in [("Taxi Zentrale", "+4933335555"), ("Anna Schmidt", "12"), ("Pizza Blitz", "+4977778888")]:
        resp = client.post("/api/phonebook", json={"name": name, "number": number, "notes": ""})
        assert resp.status_code == 200
        created_ids.append(resp.json()["id"])

    server = PhonebookLdapServer(port=0, host="127.0.0.1")
    await server.start()
    yield server
    await server.stop()
    for entry_id in created_ids:
        client.delete(f"/api/phonebook/{entry_id}")


@pytest.mark.asyncio
async def test_anonymous_bind_and_search_all_returns_every_entry(ldap_server):
    messages = await _roundtrip(
        ldap_server.port,
        _bind_request(1),
        _search_request(2, "dc=phonebook", _filter_present("objectclass")),
    )
    assert messages[0][0] == 0x61  # bindResponse
    assert messages[0][1][2] == 0  # resultCode success
    entries = [m for m in messages if m[0] == 0x64]
    assert len(entries) == 3
    assert messages[-1][0] == 0x65  # searchResultDone
    # Sorted by name: Anna first; sn/givenName split for two-word names.
    first = _entry_strings(entries[0][1])
    assert "cn=Anna Schmidt,dc=phonebook" in first
    assert "Schmidt" in first
    assert "telephoneNumber" in first


@pytest.mark.asyncio
async def test_substring_search_filters_by_name(ldap_server):
    messages = await _roundtrip(
        ldap_server.port,
        _bind_request(1),
        _search_request(
            2,
            "dc=phonebook",
            _filter_or(_filter_substrings("cn", "taxi"), _filter_substrings("sn", "taxi")),
        ),
    )
    entries = [m for m in messages if m[0] == 0x64]
    assert len(entries) == 1
    assert "Taxi Zentrale" in _entry_strings(entries[0][1])


@pytest.mark.asyncio
async def test_number_search_matches_number_field(ldap_server):
    messages = await _roundtrip(
        ldap_server.port,
        _bind_request(1),
        _search_request(2, "dc=phonebook", _filter_substrings("telephoneNumber", "7777")),
    )
    entries = [m for m in messages if m[0] == 0x64]
    assert len(entries) == 1
    assert "Pizza Blitz" in _entry_strings(entries[0][1])


@pytest.mark.asyncio
async def test_size_limit_is_respected(ldap_server):
    messages = await _roundtrip(
        ldap_server.port,
        _bind_request(1),
        _search_request(2, "dc=phonebook", _filter_present("objectclass"), size_limit=2),
    )
    entries = [m for m in messages if m[0] == 0x64]
    assert len(entries) == 2
    assert messages[-1][0] == 0x65
