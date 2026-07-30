from typing import Optional
from pydantic import ConfigDict
from sqlalchemy import Column
from sqlmodel import SQLModel, Field

from backend.crypto import EncryptedString


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


class ExtensionOut(SQLModel):
    id: int
    number: int
    display_name: str
    enabled: bool
    video_capable: bool = False
    internal_only: bool = False
    numeric_callerid: bool = False
    presence_status: str = "available"


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


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    did: str = Field(max_length=32)
    # Shared destination vocabulary with IVRMenu.options/TimeCondition:
    # "extension" | "ring_group" | "ivr" | "voicemail" | "hangup".
    destination_type: str = "extension"
    destination_id: int = 0


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


class ExtensionGroup(SQLModel, table=True):
    """A reusable named group of extensions (e.g. "Support-Team"), usable as
    a single member inside one or more RingGroups alongside individual
    extensions - not a call-handling construct itself (no ring strategy/
    timeout of its own, unlike RingGroup)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=64)
    extension_numbers: str = ""  # comma-separated list e.g. "10,11,12"


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
