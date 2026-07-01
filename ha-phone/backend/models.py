from typing import Optional
from pydantic import ConfigDict
from sqlmodel import SQLModel, Field


class Extension(SQLModel, table=True):
    model_config = ConfigDict(validate_assignment=True)

    id: Optional[int] = Field(default=None, primary_key=True)
    number: int = Field(ge=10, le=99)
    display_name: str = Field(max_length=64)
    sip_password: str = Field(default="", min_length=0)  # min enforced in router; default="" triggers auto-gen
    enabled: bool = True
    video_capable: bool = False


class ExtensionUpdate(SQLModel):
    """Partial update model — sip_password is optional (blank = keep existing)."""
    number: Optional[int] = Field(default=None, ge=10, le=99)
    display_name: Optional[str] = Field(default=None, max_length=64)
    sip_password: Optional[str] = Field(default=None, min_length=0)
    enabled: Optional[bool] = None
    video_capable: Optional[bool] = None


class Trunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    registrar_host: str = ""
    port: int = 5060
    transport: str = "udp"  # udp | tcp | tls
    domain: str = ""  # SIP domain — empty = same as registrar_host
    auth_username: str  # SIP account number — NOT the Rufnummer
    password: str  # stored in SQLite only; never written to conf in plaintext header
    phone_number: str  # CallerID / Rufnummer / DID
    reg_refresh: int = 60


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    did: str = Field(max_length=32)
    destination_type: str = "extension"  # "extension" | "ring_group"
    destination_id: int = 0


class RingGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=64)
    extension_numbers: str = ""  # comma-separated list e.g. "10,11,12"
    ring_timeout: int = 30


class TimeCondition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=64)
    did: str = Field(default="", max_length=32)   # DID matched by this condition
    open_hours_start: str = "09:00"
    open_hours_end: str = "18:00"
    open_days: str = "mon-fri"  # GotoIfTime format
    open_destination: int = 0
    closed_destination: int = 0  # 0 = voicemail


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
