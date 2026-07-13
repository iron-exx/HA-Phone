"""Minimal read-only LDAP v3 server exposing the phonebook to desk/DECT
phones (Gigaset N510/N720, Yealink, Fanvil all speak LDAP for their
"Netzverzeichnis"/remote directory feature).

Why hand-rolled: the only maintained Python LDAP *server* frameworks drag in
Twisted; the subset a phone actually uses is tiny (anonymous/simple bind +
one search per lookup, definite-length BER only), so this implements exactly
that in ~200 lines with zero new dependencies. Write operations are not
implemented at all - every entry comes fresh from the SQLite phonebook table
on each search, so the directory is always current without any sync step.

Protocol notes (RFC 4511):
- LDAPMessage ::= SEQUENCE { messageID INTEGER, protocolOp CHOICE {...} }
- BindRequest [APPLICATION 0], BindResponse [APPLICATION 1]
- UnbindRequest [APPLICATION 2] (no response, close)
- SearchRequest [APPLICATION 3], SearchResultEntry [APPLICATION 4],
  SearchResultDone [APPLICATION 5]
Everything else is answered with a protocolError result where a response
shape exists, or ignored.
"""

import asyncio
import logging
import os

from sqlmodel import Session, select

_log = logging.getLogger(__name__)

# Cap for searches that ask for "everything" (sizeLimit 0). Gigaset bases
# send their configured MaxHits as sizeLimit, so this only guards clients
# that don't.
_DEFAULT_SIZE_LIMIT = 200

# No real LDAP bind/search/filter this server ever needs to parse comes
# anywhere near this size - a client claiming a longer BER length is either
# broken or hostile. Without this cap, a single connection could declare an
# arbitrary length (up to 2**1016 per the encoding) and make readexactly()
# buffer that many bytes before returning, i.e. an unauthenticated remote
# memory-exhaustion DoS against the whole add-on (this server shares the
# FastAPI process/event loop, not a separate sandboxed one).
_MAX_MESSAGE_SIZE = 65536

# Anonymous/simple bind means anyone who can reach this port can open a
# connection and just... never send a complete message. Without a read
# deadline, each such connection parks a coroutine + a file descriptor
# forever - enough of them exhausts the process's FD limit (a slowloris-
# style DoS). Every blocking read in a connection's lifetime must go through
# this timeout, not just the first one.
_READ_TIMEOUT = 10.0

_TAG_BIND_REQUEST = 0x60
_TAG_BIND_RESPONSE = 0x61
_TAG_UNBIND_REQUEST = 0x42
_TAG_SEARCH_REQUEST = 0x63
_TAG_SEARCH_ENTRY = 0x64
_TAG_SEARCH_DONE = 0x65
_TAG_ABANDON_REQUEST = 0x50

_RESULT_SUCCESS = 0
_RESULT_PROTOCOL_ERROR = 2


# ── BER primitives ────────────────────────────────────────────────────────────
def _ber_length(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def _tlv(tag: int, content: bytes) -> bytes:
    return bytes([tag]) + _ber_length(len(content)) + content


def _ber_int(value: int, tag: int = 0x02) -> bytes:
    if value == 0:
        return _tlv(tag, b"\x00")
    body = value.to_bytes((value.bit_length() // 8) + 1, "big", signed=True)
    return _tlv(tag, body)


def _ber_str(value: str, tag: int = 0x04) -> bytes:
    return _tlv(tag, value.encode("utf-8"))


def _read_tlv(data: bytes, offset: int) -> tuple[int, bytes, int]:
    """Return (tag, content, next_offset) for the TLV at `offset`."""
    tag = data[offset]
    length = data[offset + 1]
    value_start = offset + 2
    if length & 0x80:
        num_bytes = length & 0x7F
        length = int.from_bytes(data[value_start : value_start + num_bytes], "big")
        value_start += num_bytes
    return tag, data[value_start : value_start + length], value_start + length


def _iter_tlvs(data: bytes):
    offset = 0
    while offset < len(data):
        tag, content, offset = _read_tlv(data, offset)
        yield tag, content


# ── Filter handling ───────────────────────────────────────────────────────────
def _collect_filter_needles(tag: int, content: bytes, needles: list[str]) -> None:
    """Walk an RFC 4511 filter and collect every human-typed search term.

    Phones only ever send and/or/not combinations of equalityMatch (0xA3),
    substrings (0xA4) and present (0x87). We deliberately reduce all of them
    to case-insensitive "contains" terms: the phone UI re-filters what it
    displays anyway, so being slightly too generous costs nothing, while a
    strict filter evaluator would be 10x the code for zero visible gain."""
    if tag in (0xA0, 0xA1, 0xA2):  # and / or / not - recurse
        for child_tag, child_content in _iter_tlvs(content):
            _collect_filter_needles(child_tag, child_content, needles)
    elif tag == 0xA3:  # equalityMatch: SEQ { attribute, value }
        parts = list(_iter_tlvs(content))
        if len(parts) == 2:
            needles.append(parts[1][1].decode("utf-8", errors="replace"))
    elif tag == 0xA4:  # substrings: SEQ { attribute, SEQ of initial/any/final }
        parts = list(_iter_tlvs(content))
        if len(parts) == 2:
            for _sub_tag, sub_content in _iter_tlvs(parts[1][1]):
                needles.append(sub_content.decode("utf-8", errors="replace"))
    # present (0x87) and anything else: no term - contributes "match all".


def _entry_matches(name: str, number: str, needles: list[str]) -> bool:
    if not needles:
        return True
    haystack = f"{name}\n{number}".lower()
    return any(needle.lower() in haystack for needle in needles if needle.strip())


# ── Entry rendering ───────────────────────────────────────────────────────────
def _split_name(name: str) -> tuple[str, str]:
    """(givenName, sn) - Gigaset displays sn/givenName, so a single-word name
    goes into sn (the primary sort/display field), not givenName."""
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and parts[0].strip():
        return parts[0].strip(), parts[1].strip()
    return "", name.strip()


def _attribute(attr_type: str, value: str) -> bytes:
    return _tlv(0x30, _ber_str(attr_type) + _tlv(0x31, _ber_str(value)))


def _search_entry(base_dn: str, name: str, number: str) -> bytes:
    given, sn = _split_name(name)
    dn_name = name.replace("\\", "\\\\").replace(",", "\\,")
    dn = f"cn={dn_name},{base_dn}" if base_dn else f"cn={dn_name}"
    attrs = _attribute("cn", name) + _attribute("sn", sn)
    if given:
        attrs += _attribute("givenName", given)
    attrs += _attribute("telephoneNumber", number)
    return _tlv(_TAG_SEARCH_ENTRY, _ber_str(dn) + _tlv(0x30, attrs))


def _ldap_result(tag: int, result_code: int) -> bytes:
    return _tlv(tag, _ber_int(result_code, tag=0x0A) + _ber_str("") + _ber_str(""))


def _message(message_id: int, op: bytes) -> bytes:
    return _tlv(0x30, _ber_int(message_id) + op)


# ── Server ────────────────────────────────────────────────────────────────────
class PhonebookLdapServer:
    """Serves the PhonebookEntry table read-only over LDAP."""

    def __init__(self, port: int, host: str = "0.0.0.0"):
        self._requested_port = port
        self._host = host
        self._server: asyncio.Server | None = None

    @property
    def port(self) -> int:
        assert self._server is not None
        return self._server.sockets[0].getsockname()[1]

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle_connection, self._host, self._requested_port)
        _log.info("LDAP phonebook server listening on %s:%s", self._host, self.port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def _load_entries(self) -> list[tuple[str, str]]:
        # Imported lazily so importing this module never initializes the DB.
        from backend.database import get_engine
        from backend.models import PhonebookEntry

        with Session(get_engine()) as session:
            entries = session.exec(select(PhonebookEntry)).all()
        return sorted(((e.name, e.number) for e in entries), key=lambda item: item[0].lower())

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                raw = await self._read_message(reader)
                if raw is None:
                    break
                response = self._dispatch(raw)
                if response is None:  # unbind
                    break
                if response:
                    writer.write(response)
                    await writer.drain()
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        except Exception as exc:  # noqa: BLE001 - one bad client must not kill the server
            _log.warning("LDAP connection error: %s", exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    @staticmethod
    async def _read_message(reader: asyncio.StreamReader) -> bytes | None:
        try:
            header = await asyncio.wait_for(reader.readexactly(2), _READ_TIMEOUT)
        except (asyncio.IncompleteReadError, ConnectionResetError, asyncio.TimeoutError):
            return None
        length = header[1]
        extra = b""
        if length & 0x80:
            try:
                extra = await asyncio.wait_for(reader.readexactly(length & 0x7F), _READ_TIMEOUT)
            except (asyncio.IncompleteReadError, ConnectionResetError, asyncio.TimeoutError):
                return None
            length = int.from_bytes(extra, "big")
        if length > _MAX_MESSAGE_SIZE:
            raise ValueError(f"LDAP message length {length} exceeds max {_MAX_MESSAGE_SIZE}")
        try:
            body = await asyncio.wait_for(reader.readexactly(length), _READ_TIMEOUT)
        except (asyncio.IncompleteReadError, ConnectionResetError, asyncio.TimeoutError):
            return None
        return header + extra + body

    def _dispatch(self, raw: bytes) -> bytes | None:
        """Returns response bytes, b"" for no response, or None to close."""
        tag, envelope, _ = _read_tlv(raw, 0)
        if tag != 0x30:
            return b""
        parts = list(_iter_tlvs(envelope))
        if len(parts) < 2 or parts[0][0] != 0x02:
            return b""
        message_id = int.from_bytes(parts[0][1], "big")
        op_tag, op_content = parts[1]

        if op_tag == _TAG_BIND_REQUEST:
            # Anonymous and simple binds are both accepted: the phonebook is
            # deliberately LAN-readable, same trust model as the unauthenticated
            # provisioning endpoints (secured by network, not credentials).
            return _message(message_id, _ldap_result(_TAG_BIND_RESPONSE, _RESULT_SUCCESS))
        if op_tag == _TAG_UNBIND_REQUEST:
            return None
        if op_tag == _TAG_ABANDON_REQUEST:
            return b""
        if op_tag == _TAG_SEARCH_REQUEST:
            return self._handle_search(message_id, op_content)
        # Unknown operation: most request tags have a response tag of tag+1.
        return _message(message_id, _ldap_result(op_tag + 1, _RESULT_PROTOCOL_ERROR))

    def _handle_search(self, message_id: int, content: bytes) -> bytes:
        parts = list(_iter_tlvs(content))
        # SearchRequest: baseObject, scope, derefAliases, sizeLimit, timeLimit,
        # typesOnly, filter, attributes
        base_dn = parts[0][1].decode("utf-8", errors="replace") if parts else ""
        size_limit = _DEFAULT_SIZE_LIMIT
        if len(parts) > 3 and parts[3][0] == 0x02:
            requested = int.from_bytes(parts[3][1], "big")
            if requested > 0:
                size_limit = min(requested, _DEFAULT_SIZE_LIMIT)
        needles: list[str] = []
        if len(parts) > 6:
            _collect_filter_needles(parts[6][0], parts[6][1], needles)

        try:
            entries = self._load_entries()
        except Exception as exc:  # noqa: BLE001
            _log.warning("LDAP phonebook lookup failed: %s", exc)
            entries = []

        out = b""
        sent = 0
        for name, number in entries:
            if sent >= size_limit:
                break
            if _entry_matches(name, number, needles):
                out += _message(message_id, _search_entry(base_dn, name, number))
                sent += 1
        out += _message(message_id, _ldap_result(_TAG_SEARCH_DONE, _RESULT_SUCCESS))
        return out


def ldap_port_from_env() -> int:
    try:
        return int(os.environ.get("BPX_LDAP_PORT", "389"))
    except ValueError:
        return 389
