"""Tailscale integration: API client (OAuth client credentials) and detection of
the box's own tailnet address.

HA-Phone never joins the tailnet itself. The Home Assistant Tailscale add-on does
that (host network, interface ``tailscale0``). HA-Phone only holds an OAuth client
(Tailscale console -> Trust credentials) with the scopes ``auth_keys`` and
``devices:core`` and the tag ``tag:haphone-phone``. With it, every QR pairing gets
a one-time, pre-approved auth key for the phone, and unpairing deletes the phone
from the tailnet again.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import httpx

API_BASE = "https://api.tailscale.com/api/v2"
DEFAULT_TAG = "tag:haphone-phone"
PBX_TAG = "tag:haphone-pbx"
CONSOLE_TRUST_CREDENTIALS_URL = "https://login.tailscale.com/admin/settings/trust-credentials"
KEY_EXPIRY_SECONDS = 3600  # the phone redeems the key right away
TOKEN_REFRESH_MARGIN = 300  # renew 5 min before the 1 h access token expires
HTTP_TIMEOUT = 15.0

TAILNET_V4 = ipaddress.ip_network("100.64.0.0/10")
TAILNET_V6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
TAILSCALE_IFACE = "tailscale0"

_TAG_RE = re.compile(r"^tag:[a-z0-9][a-z0-9-]{0,62}$")


class TailscaleError(Exception):
    """A Tailscale API call failed. ``message`` is German and admin-readable."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.message = message
        self.status = status


def valid_tag(tag: str) -> bool:
    return bool(_TAG_RE.match(tag or ""))


def device_hostname(extension_number: int, device_name: str) -> str:
    """Tailnet hostname for a phone, e.g. ``haphone-13-pixel-6`` (DNS label, <= 63)."""
    slug = re.sub(r"[^a-z0-9]+", "-", (device_name or "").lower()).strip("-")
    base = f"haphone-{extension_number}"
    name = f"{base}-{slug}" if slug else base
    return name[:63].rstrip("-")


# ── Own tailnet address (interface tailscale0 of the HA host) ──────────────────

SIOCGIFADDR = 0x8915


def _ipv4_of_interface(name: str) -> Optional[str]:
    import fcntl

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        packed = fcntl.ioctl(s.fileno(), SIOCGIFADDR, struct.pack("256s", name[:15].encode()))
        return socket.inet_ntoa(packed[20:24])
    except OSError:
        return None
    finally:
        s.close()


def _ipv6_of_interface(name: str, if_inet6: str = "/proc/net/if_inet6") -> Optional[str]:
    try:
        with open(if_inet6) as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    for line in lines:
        parts = line.split()
        if len(parts) >= 6 and parts[5] == name:
            addr = ipaddress.IPv6Address(int(parts[0], 16))
            if addr in TAILNET_V6:
                return str(addr)
    return None


@dataclass
class TailnetAddress:
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    # True when tailscale0 is missing: add-on not installed/running, or
    # "userspace networking" is on (then SIP/RTP can't reach the box via the tailnet).
    missing: bool = True


def detect_tailnet_address(
    ipv4_lookup: Callable[[str], Optional[str]] = _ipv4_of_interface,
    ipv6_lookup: Callable[[str], Optional[str]] = _ipv6_of_interface,
) -> TailnetAddress:
    v4 = ipv4_lookup(TAILSCALE_IFACE)
    if v4 and ipaddress.ip_address(v4) not in TAILNET_V4:
        v4 = None
    v6 = ipv6_lookup(TAILSCALE_IFACE)
    return TailnetAddress(ipv4=v4, ipv6=v6, missing=not (v4 or v6))


# ── API client ─────────────────────────────────────────────────────────────────

@dataclass
class _Token:
    value: str
    expires_at: float


@dataclass
class CheckStep:
    key: str
    ok: bool
    message: str
    warning: bool = False

    def as_dict(self) -> dict:
        return {"key": self.key, "ok": self.ok, "warning": self.warning, "message": self.message}


@dataclass
class CheckResult:
    steps: list = field(default_factory=list)
    tailnet: str = ""
    pbx_magicdns: str = ""

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)


class TailscaleClient:
    """Minimal Tailscale API v2 client. Access tokens are cached in memory only."""

    _token_cache: dict = {}
    _lock = threading.Lock()

    def __init__(self, client_id: str, client_secret: str, *, api_base: str = API_BASE,
                 transport: Optional[httpx.BaseTransport] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_base = api_base.rstrip("/")
        self._http = httpx.Client(timeout=HTTP_TIMEOUT, transport=transport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @classmethod
    def clear_token_cache(cls) -> None:
        with cls._lock:
            cls._token_cache.clear()

    # -- auth --
    def _access_token(self) -> str:
        cache_key = (self.api_base, self.client_id, self.client_secret)
        with self._lock:
            tok = self._token_cache.get(cache_key)
            if tok and tok.expires_at - TOKEN_REFRESH_MARGIN > time.time():
                return tok.value
        try:
            resp = self._http.post(
                f"{self.api_base}/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )
        except httpx.HTTPError as e:
            raise TailscaleError(f"Tailscale nicht erreichbar ({e.__class__.__name__}). Hat die Box Internet?")
        if resp.status_code in (400, 401, 403):
            raise TailscaleError("Client-ID oder Client-Secret ist falsch.", resp.status_code)
        if resp.status_code >= 400:
            raise TailscaleError(f"Anmeldung bei Tailscale fehlgeschlagen (HTTP {resp.status_code}).", resp.status_code)
        body = resp.json()
        tok = _Token(body["access_token"], time.time() + float(body.get("expires_in", 3600)))
        with self._lock:
            self._token_cache[cache_key] = tok
        return tok.value

    def _request(self, method: str, path: str, **kw) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        try:
            return self._http.request(method, f"{self.api_base}{path}", headers=headers, **kw)
        except httpx.HTTPError as e:
            raise TailscaleError(f"Tailscale nicht erreichbar ({e.__class__.__name__}).")

    @staticmethod
    def _detail(resp: httpx.Response) -> str:
        try:
            return str(resp.json().get("message", "")).strip()
        except Exception:
            return resp.text.strip()[:200]

    # -- keys --
    def create_device_key(self, tag: str, description: str) -> dict:
        """One-time, pre-approved, non-ephemeral key with ``tag``. Returns {id, key}."""
        body = {
            "capabilities": {"devices": {"create": {
                "reusable": False, "ephemeral": False, "preauthorized": True, "tags": [tag],
            }}},
            "expirySeconds": KEY_EXPIRY_SECONDS,
            # The API allows only letters, digits, spaces and dashes, max 50 chars.
            "description": re.sub(r"[^A-Za-z0-9 -]", "", description)[:50],
        }
        resp = self._request("POST", "/tailnet/-/keys", json=body)
        if resp.status_code == 403:
            raise TailscaleError("Dem Zugang fehlt das Recht „Auth Keys – Schreiben“.", 403)
        if resp.status_code == 400:
            detail = self._detail(resp)
            if "tag" in detail.lower():
                raise TailscaleError(
                    f"Tailscale erlaubt den Tag {tag} nicht. Prüfe: (1) Access controls enthält unter "
                    f"\"tagOwners\" den Eintrag {tag} und ist gespeichert, (2) der Zugang hat bei Keys \u2192 "
                    f"Auth Keys genau diesen einen Tag ({detail}).", 400)
            raise TailscaleError(f"Tailscale lehnt den Schlüssel ab: {detail}", 400)
        if resp.status_code >= 400:
            raise TailscaleError(f"Schlüssel erstellen fehlgeschlagen (HTTP {resp.status_code}): {self._detail(resp)}",
                                 resp.status_code)
        data = resp.json()
        return {"id": data.get("id", ""), "key": data.get("key", "")}

    def delete_key(self, key_id: str) -> None:
        resp = self._request("DELETE", f"/tailnet/-/keys/{key_id}")
        if resp.status_code >= 400 and resp.status_code != 404:
            raise TailscaleError(f"Schlüssel löschen fehlgeschlagen (HTTP {resp.status_code}).", resp.status_code)

    # -- devices --
    def list_devices(self) -> list:
        resp = self._request("GET", "/tailnet/-/devices")
        if resp.status_code == 403:
            raise TailscaleError("Dem Zugang fehlt das Recht „Devices Core“.", 403)
        if resp.status_code >= 400:
            raise TailscaleError(f"Geräteliste fehlgeschlagen (HTTP {resp.status_code}).", resp.status_code)
        return resp.json().get("devices", [])

    def delete_device(self, device_id: str) -> None:
        resp = self._request("DELETE", f"/device/{device_id}")
        if resp.status_code == 404:
            return
        if resp.status_code == 403:
            raise TailscaleError("Dem Zugang fehlt das Recht „Devices Core – Schreiben“.", 403)
        if resp.status_code >= 400:
            raise TailscaleError(f"Gerät entfernen fehlgeschlagen (HTTP {resp.status_code}).", resp.status_code)

    # -- live check for the admin UI --
    def forget_token(self) -> None:
        with self._lock:
            self._token_cache.pop((self.api_base, self.client_id, self.client_secret), None)

    def check(self, tag: str, pbx: TailnetAddress) -> CheckResult:
        # Scopes and tags are baked into the access token when it is issued: after the
        # admin edits the credential in the console, only a fresh token sees the change.
        self.forget_token()
        res = CheckResult()
        res.steps.append(CheckStep(
            "addon", not pbx.missing,
            f"Tailscale auf Home Assistant gefunden: {pbx.ipv4 or pbx.ipv6}" if not pbx.missing else
            "Kein Tailscale auf Home Assistant gefunden. Installiere das Add-on „Tailscale“, melde es an "
            "und lass „Userspace networking“ ausgeschaltet.",
        ))
        try:
            self._access_token()
            res.steps.append(CheckStep("login", True, "Zugang gültig."))
        except TailscaleError as e:
            res.steps.append(CheckStep("login", False, e.message))
            return res
        try:
            key = self.create_device_key(tag, "HA-Phone Verbindungstest")
            if key["id"]:
                self.delete_key(key["id"])
            res.steps.append(CheckStep("keys", True, f"Darf Geräte-Schlüssel mit {tag} erstellen."))
        except TailscaleError as e:
            res.steps.append(CheckStep("keys", False, e.message))
        try:
            devices = self.list_devices()
            res.steps.append(CheckStep("devices", True, "Darf Geräte verwalten."))
            me = find_device_by_ip(devices, pbx.ipv4, pbx.ipv6)
            if me:
                res.pbx_magicdns = (me.get("name") or "").rstrip(".")
                if "." in res.pbx_magicdns:
                    res.tailnet = res.pbx_magicdns.split(".", 1)[1]
                if PBX_TAG not in (me.get("tags") or []):
                    res.steps.append(CheckStep(
                        "pbx_tag", True,
                        f"Home Assistant hat den Tag {PBX_TAG} nicht. Das ist nur nötig, wenn deine "
                        f"Tailscale-Policy Zugriffe per Tag regelt (Add-on-Option „advertise_tags“).",
                        warning=True,
                    ))
        except TailscaleError as e:
            res.steps.append(CheckStep("devices", False, e.message))
        return res


def find_device_by_ip(devices: list, ipv4: Optional[str], ipv6: Optional[str]) -> Optional[dict]:
    wanted = {a for a in (ipv4, ipv6) if a}
    for d in devices:
        if wanted & set(d.get("addresses") or []):
            return d
    return None


ACL_SNIPPET = """\
"tagOwners": {
  "tag:haphone-phone": ["autogroup:admin"],
  "tag:haphone-pbx":   ["autogroup:admin"]
},
"grants": [
  { "src": ["tag:haphone-phone"], "dst": ["tag:haphone-pbx"],
    "ip": ["tcp:5061", "tcp:5063", "tcp:80", "udp:3478", "udp:10000-10200"] }
]"""
