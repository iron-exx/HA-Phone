from typing import List, Optional
import re

from pydantic import ConfigDict, field_validator
from sqlalchemy import Column
from sqlmodel import SQLModel, Field

from backend.conf_safety import conf_name, conf_text
from backend.crypto import EncryptedString


DOOR_OPEN_CODE_PATTERN = r"^[0-9*#]*$"
# http(s) URL without whitespace; the admin enters e.g. a Home Assistant webhook.
DOOR_WEBHOOK_PATTERN = r"^(https?://\S{1,500})?$"
# Doorbell picture source: a Home Assistant camera entity or the door station's snapshot URL.
HA_PERSON_PATTERN = r"^(person\.[a-z0-9_]{1,120})?$"
DOORBELL_CAMERA_PATTERN = r"^(camera\.[a-z0-9_]{1,120}|https?://\S{1,500})?$"
MAX_DOOR_ACTIONS = 4
# Rendered verbatim as `exten => <did>,1,...` — a comma/semicolon would inject
# dialplan priorities/comments.
DID_PATTERN = r"^[0-9+*# ()/-]*$"
# Asterisk extension pattern chars (without the leading underscore) and dial prefix.
OUTBOUND_PATTERN_RE = r"^[0-9XZNxzn.!+*#\[\]-]*$"
OUTBOUND_PREPEND_RE = r"^[0-9+*#]*$"
# SIP host / user tokens rendered into URIs (server_uri, client_uri, from_user...).
SIP_TOKEN_RE = r"^[^\s;,\[\]<>\"]*$"
CODECS_RE = r"^[a-z0-9_,]*$"
# media_encryption values the image can actually honour: res_srtp is NOT built
# (menuselect --disable-all without --enable res_srtp), so 'sdes'/'dtls' would make
# the endpoint fail to load. Legacy DB values are mapped to "none" at render time.
ALLOWED_MEDIA_ENCRYPTION = ("none",)


def _match(pattern: str, value: str | None, what: str) -> str | None:
    """sqlmodel's Field(regex=...) is not enforced on pydantic v2, so patterns are checked here."""
    if value is not None and not re.fullmatch(pattern, value):
        raise ValueError(f"{what}: ungültiges Format")
    return value


class DoorAction(SQLModel):
    """A Home Assistant service the app offers as a button in calls with this door station."""
    label: str = Field(min_length=1, max_length=24)
    service: str = Field(max_length=64)
    entity_id: str = Field(max_length=128)

    @field_validator("service")
    @classmethod
    def _service(cls, v: str) -> str:
        return _match(r"[a-z_]+\.[a-z_]+", v, "service")

    @field_validator("entity_id")
    @classmethod
    def _entity(cls, v: str) -> str:
        return _match(r"[a-z_]+\.[a-z0-9_]+", v, "entity_id")


class Extension(SQLModel, table=True):
    model_config = ConfigDict(validate_assignment=True)

    id: Optional[int] = Field(default=None, primary_key=True)
    number: int = Field(ge=10, le=99)
    display_name: str = Field(max_length=64)
    # min length enforced in router; default="" triggers auto-gen. Encrypted at
    # rest (D8) - transparent to callers, EncryptedString decrypts on read.
    sip_password: str = Field(default="", sa_column=Column(EncryptedString()))
    provisioning_token: str = Field(default="", max_length=128)
    enabled: bool = True
    video_capable: bool = False
    internal_only: bool = False  # restrict to internal calls (e.g. door intercom) — no outbound
    # Legacy-device mode: calls TO this device send only the number as display
    # name. Old clients (e.g. Android's discontinued native SIP) reject
    # non-numeric caller names and show "Anonymous" instead.
    numeric_callerid: bool = False
    # Manually-set presence status ("available" | "away" | "lunch" |
    # "do_not_disturb" | "off_work") - looked up against PresenceForwardingRule
    # at dialplan-generation time (not a live per-call lookup: the dialplan is
    # regenerated whenever this changes, same pattern as every other setting).
    presence_status: str = Field(default="available", max_length=32)
    transport: str = "udp"  # udp | tls  (D-06: TLS/SRTP test extension provisioning)
    media_encryption: str = "none"  # none | sdes | dtls
    # DTMF digits a phone sends to this (door station) extension to open the door.
    # Delivered to the mobile app via /api/mobile/directory. Empty = not a door.
    door_open_code: str = Field(default="", max_length=16, regex=DOOR_OPEN_CODE_PATTERN)
    # JSON list of DoorAction (stored as text; the API exposes a list).
    door_actions: str = Field(default="[]")
    # Lets the app record calls of this extension (MixMonitor). Off by default: recording
    # needs the consent of everyone on the call (§ 201 StGB), the admin decides per extension.
    recording_allowed: bool = False
    # Called by the PBX when the app's "Zum Öffnen schieben" slider fires (also while it
    # only rings). Empty = the app falls back to the DTMF door code during a call.
    door_open_webhook: str = Field(default="", max_length=512)
    # Where the PBX takes the doorbell picture from when this station rings (see doorbell.py).
    doorbell_camera: str = Field(default="", max_length=512)
    # Home Assistant person this extension's phone belongs to (ha_presence.py).
    ha_person: str = Field(default="", max_length=128)

    @field_validator("display_name")
    @classmethod
    def _display_name(cls, v: str) -> str:
        return conf_name(v, "display_name")


class ExtensionCreate(SQLModel):
    """Request body for POST /extensions (the table model stores door_actions as JSON text)."""
    number: int = Field(ge=10, le=99)
    display_name: str = Field(max_length=64)
    sip_password: str = ""
    enabled: bool = True
    video_capable: bool = False
    internal_only: bool = False
    numeric_callerid: bool = False
    presence_status: str = Field(default="available", max_length=32)
    transport: str = "udp"
    media_encryption: str = "none"
    door_open_code: str = Field(default="", max_length=16, regex=DOOR_OPEN_CODE_PATTERN)
    door_actions: List[DoorAction] = Field(default=[], max_length=MAX_DOOR_ACTIONS)
    recording_allowed: bool = False
    door_open_webhook: str = Field(default="", max_length=512)
    doorbell_camera: str = Field(default="", max_length=512)
    ha_person: str = Field(default="", max_length=128)

    @field_validator("ha_person")
    @classmethod
    def _ha_person(cls, v: str) -> str:
        return _match(HA_PERSON_PATTERN, v.strip(), "ha_person")

    @field_validator("door_open_code")
    @classmethod
    def _door_code(cls, v: str) -> str:
        return _match(DOOR_OPEN_CODE_PATTERN, v, "door_open_code")

    @field_validator("door_open_webhook")
    @classmethod
    def _webhook(cls, v: str) -> str:
        return _match(DOOR_WEBHOOK_PATTERN, v.strip(), "door_open_webhook")

    @field_validator("doorbell_camera")
    @classmethod
    def _doorbell_camera(cls, v: str) -> str:
        return _match(DOORBELL_CAMERA_PATTERN, v.strip(), "doorbell_camera")

    @field_validator("display_name")
    @classmethod
    def _display_name(cls, v):
        return conf_name(v, "display_name")

    @field_validator("sip_password")
    @classmethod
    def _sip_password(cls, v):
        return conf_text(v, "sip_password")

    @field_validator("media_encryption")
    @classmethod
    def _media_encryption(cls, v):
        if v is not None and v not in ALLOWED_MEDIA_ENCRYPTION:
            raise ValueError("media_encryption: SRTP wird nicht unterstützt (res_srtp nicht gebaut) — nur 'none'")
        return v


class ExtensionUpdate(SQLModel):
    """Partial update model — sip_password is optional (blank = keep existing)."""
    number: Optional[int] = Field(default=None, ge=10, le=99)
    display_name: Optional[str] = Field(default=None, max_length=64)
    sip_password: Optional[str] = Field(default=None, min_length=0)
    enabled: Optional[bool] = None
    video_capable: Optional[bool] = None
    internal_only: Optional[bool] = None
    numeric_callerid: Optional[bool] = None
    presence_status: Optional[str] = Field(default=None, max_length=32)
    transport: Optional[str] = Field(default=None, max_length=8)
    media_encryption: Optional[str] = Field(default=None, max_length=8)
    door_open_code: Optional[str] = Field(default=None, max_length=16, regex=DOOR_OPEN_CODE_PATTERN)
    door_actions: Optional[List[DoorAction]] = Field(default=None, max_length=MAX_DOOR_ACTIONS)
    recording_allowed: Optional[bool] = None
    door_open_webhook: Optional[str] = Field(default=None, max_length=512)
    doorbell_camera: Optional[str] = Field(default=None, max_length=512)
    ha_person: Optional[str] = Field(default=None, max_length=128)

    @field_validator("ha_person")
    @classmethod
    def _ha_person(cls, v: str | None) -> str | None:
        return None if v is None else _match(HA_PERSON_PATTERN, v.strip(), "ha_person")

    @field_validator("door_open_code")
    @classmethod
    def _door_code(cls, v: str | None) -> str | None:
        return _match(DOOR_OPEN_CODE_PATTERN, v, "door_open_code")

    @field_validator("door_open_webhook")
    @classmethod
    def _webhook(cls, v: str | None) -> str | None:
        return None if v is None else _match(DOOR_WEBHOOK_PATTERN, v.strip(), "door_open_webhook")

    @field_validator("doorbell_camera")
    @classmethod
    def _doorbell_camera(cls, v: str | None) -> str | None:
        return None if v is None else _match(DOORBELL_CAMERA_PATTERN, v.strip(), "doorbell_camera")

    @field_validator("display_name")
    @classmethod
    def _display_name(cls, v):
        return conf_name(v, "display_name")

    @field_validator("sip_password")
    @classmethod
    def _sip_password(cls, v):
        return conf_text(v, "sip_password")

    @field_validator("media_encryption")
    @classmethod
    def _media_encryption(cls, v):
        if v is not None and v not in ALLOWED_MEDIA_ENCRYPTION:
            raise ValueError("media_encryption: SRTP wird nicht unterstützt (res_srtp nicht gebaut) — nur 'none'")
        return v


class ExtensionOut(SQLModel):
    id: int
    number: int
    display_name: str
    enabled: bool
    video_capable: bool = False
    internal_only: bool = False
    numeric_callerid: bool = False
    presence_status: str = "available"
    door_open_code: str = ""
    door_actions: List[dict] = []
    recording_allowed: bool = False
    door_open_webhook: str = ""
    doorbell_camera: str = ""
    ha_person: str = ""


class ExtensionCreateOut(ExtensionOut):
    sip_password: str


class PresenceForwardingRule(SQLModel, table=True):
    """Overrides what happens to a call reaching this extension while it is
    in a specific presence status, separately for internal vs external calls.
    At most one row per (extension_id, status, direction) - resolved once at
    dialplan-generation time against the extension's CURRENT presence_status
    (not a live per-call lookup, per the "manual toggle" design: changing
    presence_status regenerates the dialplan, same as every other setting).

    No row for a given (extension, status, direction) = today's unchanged
    default behavior (ring the extension, then its own voicemail on no-answer).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    extension_id: int
    status: str = Field(max_length=32)  # matches Extension.presence_status values
    direction: str = Field(max_length=16)  # "internal" | "external"
    # "ring_then_dest": ring the extension for ring_timeout seconds, then go to
    # dest_type/dest_target on no-answer (like today's default, but to a
    # different destination than the extension's own voicemail).
    # "always_dest": skip ringing entirely, go straight to dest_type/dest_target.
    mode: str = Field(default="ring_then_dest", max_length=16)
    # Shared destination vocabulary with Route/IVRMenu.options/TimeCondition:
    # "extension" | "ring_group" | "ivr" | "voicemail" | "hangup". Targets use
    # the same convention as Route/TimeCondition (extension/voicemail by
    # number, ring_group/ivr by DB id).
    dest_type: str = Field(default="voicemail", max_length=16)
    dest_target: int = 0
    ring_timeout: int = 20


class ProvisioningTemplate(SQLModel, table=True):
    """User-editable auto-provisioning template (like Yeastar/3CX custom templates).

    `content` is the raw device config with placeholders that are substituted when a
    device fetches its config: {{mac}} {{extension}} {{display_name}} {{sip_username}}
    {{sip_password}} {{sip_server}} {{sip_port}} {{label}}.
    `file_pattern` is how the device requests its file, e.g. "{mac}.cfg" or "{mac}.xml".
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=96)
    vendor: str = Field(default="", max_length=48)
    file_pattern: str = Field(default="{mac}.cfg", max_length=64)
    content: str = ""
    builtin: bool = False


class ProvisionedDevice(SQLModel, table=True):
    """A physical endpoint (desk phone, DECT base, door station) that fetches its
    config from HA-Phone by MAC and registers the assigned extension(s)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="", max_length=96)
    manufacturer: str = Field(default="", max_length=48)
    model: str = Field(default="", max_length=64)
    mac: str = Field(default="", max_length=32)   # normalized: lowercase, no separators
    # Comma-separated Extension.number values, in provisioning order (mirrors
    # RingGroup.extension_numbers). A multi-line device (DECT base with several
    # handsets) needs one SIP account per handset, not one shared account -
    # sharing hits the AOR's max_contacts and the base has no line to dial out
    # on for any handset beyond the first.
    extension_numbers: str = ""
    template_id: int = 0
    extra_vars: str = Field(default="{}")  # JSON dict of per-device template variables


class Trunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    registrar_host: str = ""
    port: int = 5060
    transport: str = "udp"  # udp | tcp | tls
    domain: str = ""  # SIP domain — empty = same as registrar_host
    auth_username: str  # SIP account number — NOT the Rufnummer
    password: str = Field(sa_column=Column(EncryptedString()))  # encrypted at rest (D8)
    phone_number: str  # CallerID / Rufnummer / DID
    reg_refresh: int = 60
    codecs: str = "ulaw,alaw"  # comma-separated Asterisk codec names, in priority order
    # Dial(...,r): the PBX signals "ringing" (180) to the caller itself, so the phone plays
    # its own ringback. Without it callers heard silence when the provider sends a 183
    # without audio. Off = pass the provider's early media (announcements) through.
    local_ringback: bool = True

    @field_validator("registrar_host", "domain", "auth_username", "phone_number")
    @classmethod
    def _sip_token(cls, v: str, info) -> str:
        conf_text(v, info.field_name)
        return _match(SIP_TOKEN_RE, v, info.field_name)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return conf_text(v, "password")

    @field_validator("codecs")
    @classmethod
    def _codecs(cls, v: str) -> str:
        return _match(CODECS_RE, v.replace(" ", ""), "codecs")

    @field_validator("transport")
    @classmethod
    def _transport(cls, v: str) -> str:
        return _match(r"^(udp|tcp|tls)$", v, "transport")


class TrunkDid(SQLModel, table=True):
    """An additional phone number (DID) reachable via the trunk, beyond
    Trunk.phone_number (the primary/registered number). Reference list only —
    used to populate DID pickers (Route.did, OutboundRule.outbound_caller_id)
    instead of free-typing numbers; the SIP registration identity itself stays
    tied to the single primary phone_number (aarenet/DG convention).

    No trunk_id: HA-Phone only ever has one Trunk row, and `save_trunk`
    deletes+recreates it (new id) on every save, which would orphan a foreign
    key on every trunk edit. A flat list is simpler and avoids that entirely.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    did: str = Field(max_length=32)
    label: str = Field(default="", max_length=64)

    @field_validator("did")
    @classmethod
    def _did(cls, v: str) -> str:
        return _match(DID_PATTERN, v, "did")


class SmtpSettings(SQLModel, table=True):
    """Outbound mail (SMTP) for sending voicemail-to-email. Single row."""
    id: Optional[int] = Field(default=None, primary_key=True)
    host: str = Field(default="", max_length=128)
    port: int = 587
    encryption: str = Field(default="starttls", max_length=16)  # starttls | ssl | none
    username: str = Field(default="", max_length=128)
    password: str = Field(default="", sa_column=Column(EncryptedString()))  # encrypted at rest (D8)
    from_addr: str = Field(default="", max_length=128)
    from_name: str = Field(default="HA-Phone", max_length=64)
    enabled: bool = False

    @field_validator("host", "username", "password", "from_addr")
    @classmethod
    def _text(cls, v: str, info) -> str:
        return conf_text(v, info.field_name)

    @field_validator("from_name")
    @classmethod
    def _from_name(cls, v: str) -> str:
        return conf_name(v, "from_name")


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    did: str = Field(max_length=32)
    # Shared destination vocabulary with IVRMenu.options/TimeCondition:
    # "extension" | "ring_group" | "ivr" | "voicemail" | "hangup".
    destination_type: str = "extension"
    destination_id: int = 0

    @field_validator("did")
    @classmethod
    def _did(cls, v: str) -> str:
        return _match(DID_PATTERN, v, "did")


class OutboundRule(SQLModel, table=True):
    """Editable outbound dial-pattern rule (like the Yeastar 'Ausgehende Leitung').

    A dialed number matching `pattern` (an Asterisk extension pattern WITHOUT the
    leading underscore, e.g. "0." or "00." or "+.") has `strip` leading digits
    removed and `prepend` prepended, then is routed to the SIP trunk. Lower
    `priority` is evaluated/shown first.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    pattern: str = Field(default="", max_length=32)
    strip: int = 0
    prepend: str = Field(default="", max_length=16)
    priority: int = 0
    # Optional per-rule outbound CallerID override (one of the trunk's DIDs).
    # Empty = fall back to the trunk's default phone_number, same as before
    # this field existed.
    outbound_caller_id: str = Field(default="", max_length=32)

    @field_validator("pattern")
    @classmethod
    def _pattern(cls, v: str) -> str:
        return _match(OUTBOUND_PATTERN_RE, v, "pattern")

    @field_validator("prepend")
    @classmethod
    def _prepend(cls, v: str) -> str:
        return _match(OUTBOUND_PREPEND_RE, v, "prepend")

    @field_validator("outbound_caller_id")
    @classmethod
    def _cid(cls, v: str) -> str:
        return _match(DID_PATTERN, v, "outbound_caller_id")


class ExtensionGroup(SQLModel, table=True):
    """A reusable named group of extensions (e.g. "Support-Team"), usable as
    a single member inside one or more RingGroups alongside individual
    extensions - not a call-handling construct itself (no ring strategy/
    timeout of its own, unlike RingGroup)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=64)
    extension_numbers: str = ""  # comma-separated list e.g. "10,11,12"
    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return conf_name(v, "name")


class RingGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    number: int = Field(default=0, ge=0, le=99)
    name: str = Field(max_length=64)
    extension_numbers: str = ""  # comma-separated list e.g. "10,11,12"
    # Additive, not a replacement of extension_numbers above: comma-separated
    # ExtensionGroup.id values whose members also get dialed. Kept as a
    # separate field (not merged into extension_numbers) so existing rows/
    # parsing code elsewhere (frontend split(",") call sites, dial-string
    # building) keep working unchanged for groups that don't use this.
    extension_group_ids: str = ""
    ring_timeout: int = 30

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return conf_name(v, "name")


class IVRMenu(SQLModel, table=True):
    """Interactive Voice Response menu (digitaler Empfang).
    Callers hear a greeting and press keys to reach extensions, ring groups, etc."""
    id: Optional[int] = Field(default=None, primary_key=True)
    number: int = Field(default=0, ge=10, le=99)  # internal extension number to reach this IVR
    name: str = Field(max_length=64)  # e.g. "Hauptmenu"
    greeting_file: str = ""  # filename of uploaded WAV greeting in /data/sounds/custom/ivr/
    timeout: int = 10  # seconds to wait for DTMF input
    max_invalid_tries: int = 3  # replay menu this many times on invalid input
    options: str = ""  # JSON array: [{"key":"1","action":"extension","target":10,"label":"Verkauf"}, ...]
    # action types: "extension", "ring_group", "ivr", "voicemail", "hangup"

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return conf_name(v, "name")


class TimeCondition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=64)
    did: str = Field(default="", max_length=32)   # DID matched by this condition
    open_hours_start: str = "09:00"
    open_hours_end: str = "18:00"
    open_days: str = "mon-fri"  # GotoIfTime format
    # Destination vocabulary shared with Route/IVRMenu.options: dest_type is one
    # of "extension" | "ring_group" | "ivr" | "voicemail" | "hangup"; *_destination
    # holds the target id/number (unused for "hangup"). Kept as two separate int
    # fields (not renamed) for migration simplicity — dest_type defaults to
    # "extension" so pre-existing rows keep their old plain-extension behavior.
    open_destination: int = 0
    open_dest_type: str = "extension"
    closed_destination: int = 0
    # Defaults to "voicemail", not "extension": pre-existing rows always routed
    # straight to Voicemail(closed_destination@default,u) with no Dial() at all,
    # so "voicemail" is the type that preserves that behavior after migration.
    closed_dest_type: str = "voicemail"

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return conf_name(v, "name")

    @field_validator("did")
    @classmethod
    def _did(cls, v: str) -> str:
        return _match(DID_PATTERN, v, "did")

    @field_validator("open_hours_start", "open_hours_end")
    @classmethod
    def _hhmm(cls, v: str, info) -> str:
        return _match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", v, info.field_name)

    @field_validator("open_days")
    @classmethod
    def _days(cls, v: str) -> str:
        return _match(r"^[a-z*&,-]*$", v, "open_days")


class Holiday(SQLModel, table=True):
    """A one-time closure day (Roadmap Phase B.3) applied to every
    TimeCondition: on this exact year/month/day, calls are routed to
    closed_destination regardless of open_hours/open_days. Deliberately NOT
    auto-recurring - most holiday dates shift from year to year (Easter and
    everything calculated from it, plus bridge days chosen per year), so a
    fixed month/day would silently apply on the wrong date in later years.
    Users re-add/import next year's dates instead (see CSV import)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=64)
    year: int = Field(ge=1970, le=2200)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return conf_text(v, "name")


class PhonebookEntry(SQLModel, table=True):
    """Company/personal directory entry (Roadmap 'Prioritaet Hoch': Telefonbuch
    mit CSV-Import/Export). Not yet wired into the dialplan for inbound
    CallerID-name lookup - CRUD + CSV first, per the roadmap's own ticket
    scope; that enrichment is a natural follow-up, not done here."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=96)
    number: str = Field(max_length=32)
    notes: str = Field(default="", max_length=256)


class VoicemailSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    extension_id: int
    mailbox: str
    email: str = ""
    attach_message: bool = False
    delete_after_email: bool = False


class AdminUser(SQLModel, table=True):
    """Single admin user for web UI authentication (SEC-04, D-08)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = "admin"          # always "admin" — single-user setup
    hashed_password: bytes           # bcrypt output — SQLModel maps bytes to BLOB
    must_change_password: bool = True

# ============================================================
# MOBILE APP PROVISIONING (Phase 3: QR Code / JWT based)
# ============================================================

import secrets
from datetime import datetime, timedelta

class MobileDevice(SQLModel, table=True):
    """A mobile device (iOS/Android) provisioned via QR code.
    Linked to an Extension, stores FCM/APNs push token and device identity.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    extension_id: int = Field(foreign_key="extension.id")
    # Platform: "ios" | "android"
    platform: str = Field(max_length=16)
    # FCM token (Android) or APNs token (iOS) - encrypted at rest
    push_token: str = Field(default="", sa_column=Column(EncryptedString()))
    # Unique device identifier from OS (Android: ANDROID_ID, iOS: identifierForVendor)
    os_device_id: str = Field(default="", max_length=128)
    # App version that provisioned this device
    app_version: str = Field(default="", max_length=32)
    # Human-readable device name (e.g. "Sandro's iPhone 15")
    device_name: str = Field(default="", max_length=96)
    # Provisioning status: "pending" | "active" | "revoked"
    status: str = Field(default="pending", max_length=16)
    # JWT token used for provisioning (one-time, short-lived)
    provisioning_jwt_jti: str = Field(default="", max_length=64)
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: Optional[datetime] = None
    # Optional: last known IP for diagnostics
    last_ip: str = Field(default="", max_length=45)
    # SHA-256 hex of the per-device secret handed out once by /provision/complete.
    # Every phone-facing endpoint authenticates with device_id + that secret.
    device_token_hash: str = Field(default="", max_length=64)
    # Tailscale node of this phone (StableNodeID + 100.x), reported by the app after
    # joining; used to delete the phone from the tailnet on unpairing.
    tailscale_node_id: str = Field(default="", max_length=64)
    tailscale_ip: str = Field(default="", max_length=45)


class TailnetConfig(SQLModel, table=True):
    """Tailscale access (OAuth client / trust credential) for phone auth keys. Single row."""
    id: Optional[int] = Field(default=None, primary_key=True)
    enabled: bool = Field(default=True)  # hand out keys on new QR pairings
    client_id: str = Field(default="", max_length=128)
    client_secret: str = Field(default="", sa_column=Column(EncryptedString()))
    tag: str = Field(default="tag:haphone-phone", max_length=64)
    tailnet: str = Field(default="", max_length=128)
    pbx_magicdns: str = Field(default="", max_length=255)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProvisioningToken(SQLModel):
    """Request model for POST /api/mobile/provision/start"""
    extension_number: int
    platform: str  # "ios" | "android"
    device_name: str = ""
    # Optional: app version
    app_version: str = ""


class ProvisioningTokenOut(SQLModel):
    """Response model for POST /api/mobile/provision/start"""
    provisioning_token: str  # JWT token (Ed25519 signed)
    qr_code_url: str  # haphone://provision?t=<JWT> or https://...
    expires_at: datetime


class ProvisioningCompleteIn(SQLModel):
    """Request model for POST /api/mobile/provision/complete"""
    provisioning_token: str  # JWT from QR code
    push_token: str  # FCM token (Android) or APNs token (iOS)
    os_device_id: str
    app_version: str = ""
    device_name: str = ""


class ProvisioningCompleteOut(SQLModel):
    """Response model for POST /api/mobile/provision/complete"""
    success: bool
    device_id: int
    # Long-lived device secret, returned only here; the server keeps just its hash.
    device_token: str
    extension_number: int
    sip_domain: str
    sip_username: str
    sip_password: str
    sip_port: int
    transport: str  # "tls"
    stun_servers: List[str]
    turn_servers: List[str]
    codecs: List[str]
    config_version: int
    # Present only when Tailscale is set up in HA-Phone (see backend/tailnet.py).
    tailscale: Optional[dict] = None


class DeviceRegisterIn(SQLModel):
    """Request model for POST /api/mobile/device/register"""
    device_id: int
    device_token: str
    push_token: str
    os_device_id: str
    app_version: str = ""


class DeviceRegisterOut(SQLModel):
    success: bool
    device_id: int


class DeviceRevokeIn(SQLModel):
    """Request model for POST /api/mobile/device/revoke"""
    device_id: int
    extension_number: int  # for authorization


class PushTokenRefreshIn(SQLModel):
    """Request model for POST /api/mobile/device/refresh-token"""
    device_id: int
    device_token: str
    push_token: str
    os_device_id: str


class MobileDeviceOut(SQLModel):
    """Output model for device listing"""
    id: int
    extension_number: int
    platform: str
    device_name: str
    status: str
    app_version: str
    created_at: datetime
    last_seen_at: Optional[datetime]
    last_ip: str
    tailscale_ip: str = ""




# ── Config-injection checks for table models used directly as request bodies ──
# SQLModel table models (table=True) do NOT run field validators when FastAPI
# parses a request body into them, so the @field_validator methods above only fire
# on model_validate(). Routers call validate_conf_fields() explicitly instead —
# it checks just the fields that are rendered into .conf files.
def _did(v, what):
    return _match(DID_PATTERN, v, what)


def _sip_token(v, what):
    conf_text(v, what)
    return _match(SIP_TOKEN_RE, v, what)


_CONF_FIELD_CHECKS = {
    "RingGroup": {"name": conf_name},
    "IVRMenu": {"name": conf_name, "greeting_file": conf_text},
    "Holiday": {"name": conf_text},  # only rendered into a dialplan comment
    "ExtensionGroup": {"name": conf_name},
    "TimeCondition": {
        "name": conf_name, "did": _did,
        "open_hours_start": lambda v, w: _match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", v, w),
        "open_hours_end": lambda v, w: _match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", v, w),
        "open_days": lambda v, w: _match(r"^[a-z*&,-]*$", v, w),
    },
    "Route": {"did": _did},
    "TrunkDid": {"did": _did, "label": conf_text},
    "OutboundRule": {
        "pattern": lambda v, w: _match(OUTBOUND_PATTERN_RE, v, w),
        "prepend": lambda v, w: _match(OUTBOUND_PREPEND_RE, v, w),
        "outbound_caller_id": _did,
    },
    "Trunk": {
        "registrar_host": _sip_token, "domain": _sip_token,
        "auth_username": _sip_token, "phone_number": _sip_token,
        "password": conf_text,
        "codecs": lambda v, w: _match(CODECS_RE, (v or "").replace(" ", ""), w),
        "transport": lambda v, w: _match(r"^(udp|tcp|tls)$", v, w),
    },
}


def validate_conf_fields(obj) -> None:
    """Raise HTTP 422 if a conf-rendered field of this table model is unsafe."""
    from fastapi import HTTPException

    checks = _CONF_FIELD_CHECKS.get(type(obj).__name__, {})
    for field, check in checks.items():
        value = getattr(obj, field, None)
        if not isinstance(value, str):
            continue
        try:
            check(value, field)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))


class DoorbellEvent(SQLModel, table=True):
    """One ring at a door station (doorbell.py). Kept 30 days / 500 events."""
    id: Optional[int] = Field(default=None, primary_key=True)
    door_number: int = Field(index=True)
    door_name: str = Field(default="", max_length=64)
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    ended_at: Optional[datetime] = None
    answered_by: str = Field(default="", max_length=64)
    door_opened: bool = False
    # File name under /data/doorbell (never taken from a request).
    image_file: str = Field(default="", max_length=128)
