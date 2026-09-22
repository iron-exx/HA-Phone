"""
Mobile App Provisioning API (Phase 3: QR Code / JWT based)
Endpoints for iOS/Android app QR-code provisioning and push-token management.
"""
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import (
    Extension,
    MobileDevice,
    ProvisioningToken,
    ProvisioningTokenOut,
    ProvisioningCompleteIn,
    ProvisioningCompleteOut,
    DeviceRegisterIn,
    DeviceRegisterOut,
    DeviceRevokeIn,
    PushTokenRefreshIn,
    MobileDeviceOut,
)
from backend.auth import get_current_user as get_current_admin_user
from backend.crypto import EncryptedString

# Admin-gated CRUD/control router (start provisioning, revoke, list devices).
router = APIRouter(prefix="/mobile", tags=["mobile-provisioning"])
# PUBLIC router — the phone only ever has the one-time provisioning JWT, never
# an admin session, so these must be reachable unauthenticated.
public_router = APIRouter(prefix="/mobile", tags=["mobile-provisioning"])

# ============================================================
# JWT Helpers (Ed25519 signed provisioning tokens)
# ============================================================
import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# TODO: Move to config/settings - load a persisted key from file so tokens
# survive a process restart, instead of a fresh ephemeral pair every start.
#
# Was: two independent hand-typed placeholder PEM strings ("QqQqQq..."),
# each just valid-enough-looking base64/DER for Ed25519's fixed 32-byte key
# format to parse WITHOUT raising -- so the try below silently succeeded
# with a PRIVATE_KEY and PUBLIC_KEY that were never actually derived from
# each other, i.e. not a real matching pair. Every signature made with
# PRIVATE_KEY then failed to verify against PUBLIC_KEY, making
# verify_provisioning_jwt() reject every token as an invalid signature --
# the entire QR-provisioning flow was broken regardless of anything else
# being correct. Confirmed by generating+verifying a token in the same
# process before this fix (InvalidSignatureError) and after (passes).
# Generating a real ephemeral pair (private key derives its own public key)
# is what the surrounding comment already intended as the "dev" behavior;
# this just makes that the only path instead of a normally-untaken except
# branch guarding two mismatched fakes.
PRIVATE_KEY = Ed25519PrivateKey.generate()
PUBLIC_KEY = PRIVATE_KEY.public_key()

PROVISIONING_TOKEN_TTL_MINUTES = 5  # short-lived for security
JWT_ALGORITHM = "EdDSA"


def _lan_ip() -> str:
    """Best-effort primary LAN IPv4 of the host."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


def create_provisioning_jwt(extension_number: int, platform: str, device_name: str = "") -> str:
    """Create a short-lived Ed25519 signed JWT for QR code provisioning."""
    # datetime.utcnow() is naive -- .timestamp() on a naive datetime assumes
    # LOCAL time, so on a non-UTC host (e.g. CCsrv, Europe/Berlin/CEST =
    # UTC+2) this silently computed iat/exp ~2h in the past, making every
    # token appear already expired the instant it was checked. Must use an
    # aware UTC datetime so .timestamp() converts correctly regardless of
    # the host's local timezone.
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=PROVISIONING_TOKEN_TTL_MINUTES)
    jti = secrets.token_urlsafe(16)

    payload = {
        "sub": str(extension_number),
        "purpose": "provision",
        "platform": platform,
        "device_name": device_name,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": jti,
        "v": 1,  # version
    }

    # EdDSA signing (PyJWT 2.8+ supports EdDSA)
    token = jwt.encode(payload, PRIVATE_KEY, algorithm=JWT_ALGORITHM)
    return token


def verify_provisioning_jwt(token: str) -> dict:
    """Verify and decode provisioning JWT. Returns payload or raises HTTPException."""
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Provisioning token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=400, detail=f"Invalid provisioning token: {e}")

    if payload.get("purpose") != "provision":
        raise HTTPException(status_code=400, detail="Token purpose mismatch")

    return payload


# ============================================================
# Helper Functions
# ============================================================

def _lan_ip() -> str:
    """Best-effort primary LAN IPv4 of the host."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


def get_extension_by_number(session: Session, number: int) -> Extension:
    ext = session.exec(select(Extension).where(Extension.number == number)).first()
    if not ext:
        raise HTTPException(status_code=404, detail=f"Extension {number} not found")
    return ext


def get_mobile_device_by_id(session: Session, device_id: int) -> MobileDevice:
    device = session.get(MobileDevice, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Mobile device not found")
    return device


def get_client_ip(request: Request) -> str:
    """Extract client IP from request (handles proxies)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


# ============================================================
# API Endpoints
# ============================================================

# --- POST /api/mobile/provision/start ---
# Admin initiates provisioning: generates JWT + QR code URL
@router.post("/provision/start", response_model=ProvisioningTokenOut)
def start_provisioning(
    data: ProvisioningToken,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_admin_user),
):
    """Generate a one-time provisioning JWT + QR code URL.
    Admin must be authenticated. Returns JWT + QR code URL for user to scan.
    """
    ext = get_extension_by_number(session, data.extension_number)
    if not ext.enabled:
        raise HTTPException(status_code=400, detail="Extension is disabled")

    # Validate platform
    if data.platform not in ("ios", "android"):
        raise HTTPException(status_code=400, detail="Platform must be 'ios' or 'android'")

    # Create JWT
    jwt_token = create_provisioning_jwt(
        extension_number=data.extension_number,
        platform=data.platform,
        device_name=data.device_name or f"{ext.display_name}'s {data.platform.capitalize()}",
    )

    # QR code URL - supports both custom scheme and universal link.
    # Backend is plain HTTP on port 80 directly (host_network, no Docker
    # port remap) — embed the bare LAN IP so the phone knows which box to
    # talk to; no port needed.
    qr_url = f"haphone://provision?t={jwt_token}&host={_lan_ip()}"
    # Also support universal link for App Store distribution
    # universal_url = f"https://{_lan_ip()}/app/setup?t={jwt_token}"

    # Decode to get expiry for response
    import jwt as jwt_lib
    payload = jwt_lib.decode(jwt_token, PUBLIC_KEY, algorithms=[JWT_ALGORITHM])
    exp = datetime.fromtimestamp(payload["exp"])

    return ProvisioningTokenOut(
        provisioning_token=jwt_token,
        qr_code_url=qr_url,
        expires_at=exp,
    )


# --- POST /api/mobile/provision/complete ---
# Mobile app completes provisioning after QR scan (PUBLIC — only has the JWT)
@public_router.post("/provision/complete", response_model=ProvisioningCompleteOut)
async def complete_provisioning(
    data: ProvisioningCompleteIn,
    request: Request,
    session: Session = Depends(get_session),
):
    """Complete provisioning after QR code scan.
    Mobile app sends JWT + push token + device info.
    Returns SIP config for the app to use.
    """
    # Verify JWT
    payload = verify_provisioning_jwt(data.provisioning_token)

    extension_number = int(payload["sub"])
    platform = payload["platform"]
    jti = payload["jti"]

    ext = get_extension_by_number(session, extension_number)

    # Check if device with this JTI already exists (prevent replay)
    existing = session.exec(
        select(MobileDevice).where(MobileDevice.provisioning_jwt_jti == payload["jti"])
    ).first()
    if existing:
        # Update existing device (idempotent)
        device = existing
    else:
        device = MobileDevice(
            extension_id=ext.id,
            platform=platform,
            os_device_id=data.os_device_id,
            app_version=data.app_version,
            device_name=data.device_name or payload.get("device_name", ""),
            provisioning_jwt_jti=jti,
            status="active",
        )

    # Update device info
    device.push_token = data.push_token
    device.os_device_id = data.os_device_id
    device.app_version = data.app_version
    device.device_name = data.device_name or device.device_name
    device.status = "active"
    device.updated_at = datetime.utcnow()
    device.last_seen_at = datetime.utcnow()
    device.last_ip = get_client_ip(request)

    session.add(device)
    session.commit()
    session.refresh(device)

    # Return SIP config for the app
    return ProvisioningCompleteOut(
        success=True,
        device_id=device.id,
        extension_number=ext.number,
        sip_domain=f"{_lan_ip()}:5061",  # TLS port
        sip_username=str(ext.number),
        sip_password=ext.sip_password,  # decrypted by EncryptedString
        sip_port=5061,
        transport="tls",
        stun_servers=[f"stun:{_lan_ip()}:3478"],
        turn_servers=[],  # TODO: add TURN if configured
        codecs=["opus", "g722", "ulaw", "alaw"],
        config_version=1,
    )


# --- POST /api/mobile/device/register ---
# Register/update push token for existing device (PUBLIC — only has the JWT)
@public_router.post("/device/register", response_model=DeviceRegisterOut)
def register_device(
    data: DeviceRegisterIn,
    request: Request,
    session: Session = Depends(get_session),
):
    """Register or update push token for an existing mobile device.
    Called by app on startup or when push token changes.
    """
    device = get_mobile_device_by_id(session, data.device_id)

    device.push_token = data.push_token
    device.os_device_id = data.os_device_id
    device.app_version = data.app_version
    device.updated_at = datetime.utcnow()
    device.last_seen_at = datetime.utcnow()
    device.last_ip = get_client_ip(request)

    session.add(device)
    session.commit()

    return DeviceRegisterOut(success=True, device_id=device.id)


# --- POST /api/mobile/device/refresh-token ---
# Refresh push token (same as register but explicit) (PUBLIC — only has the JWT)
@public_router.post("/device/refresh-token", response_model=DeviceRegisterOut)
def refresh_push_token(
    data: PushTokenRefreshIn,
    request: Request,
    session: Session = Depends(get_session),
):
    """Refresh push token for existing device."""
    return register_device(
        DeviceRegisterIn(
            device_id=data.device_id,
            push_token=data.push_token,
            os_device_id=data.os_device_id,
            app_version="",
        ),
        request,
        session,
    )


# --- POST /api/mobile/device/revoke ---
# Admin revokes a mobile device
@router.post("/device/revoke")
def revoke_device(
    data: DeviceRevokeIn,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_admin_user),
):
    """Admin revokes a mobile device (logs out, clears push token)."""
    ext = get_extension_by_number(session, data.extension_number)
    device = get_mobile_device_by_id(session, data.device_id)

    if device.extension_id != ext.id:
        raise HTTPException(status_code=403, detail="Device does not belong to this extension")

    device.status = "revoked"
    device.push_token = ""
    device.updated_at = datetime.utcnow()
    session.add(device)
    session.commit()

    return {"success": True, "message": "Device revoked"}


# --- GET /api/mobile/devices ---
# Admin lists all mobile devices for an extension
@router.get("/devices/{extension_number}", response_model=List[MobileDeviceOut])
def list_mobile_devices(
    extension_number: int,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_admin_user),
):
    """Admin lists all mobile devices for an extension."""
    ext = get_extension_by_number(session, extension_number)

    devices = session.exec(
        select(MobileDevice).where(MobileDevice.extension_id == ext.id)
    ).all()

    result = []
    for d in devices:
        result.append(MobileDeviceOut(
            id=d.id,
            extension_number=extension_number,
            platform=d.platform,
            device_name=d.device_name,
            status=d.status,
            app_version=d.app_version,
            created_at=d.created_at,
            last_seen_at=d.last_seen_at,
            last_ip=d.last_ip,
        ))
    return result


# --- GET /api/mobile/config ---
# Mobile app fetches current SIP config (after provisioning) (PUBLIC — only has the JWT)
@public_router.get("/config")
def get_mobile_config(
    extension_number: int,
    session: Session = Depends(get_session),
):
    """Mobile app fetches current SIP config (after initial provisioning).
    Used for re-config or when app needs fresh config.
    """
    ext = get_extension_by_number(session, extension_number)

    return {
        "extension_number": ext.number,
        "sip_domain": f"{_lan_ip()}:5061",
        "sip_username": str(ext.number),
        "sip_password": ext.sip_password,
        "sip_port": 5061,
        "transport": "tls",
        "stun_servers": [f"stun:{_lan_ip()}:3478"],
        "turn_servers": [],
        "codecs": ["opus", "g722", "ulaw", "alaw"],
        "config_version": 1,
    }

