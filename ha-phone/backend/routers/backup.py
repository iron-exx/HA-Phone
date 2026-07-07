"""Backup/Restore (Roadmap Phase B.4). Exports the full PBX configuration
(everything except the admin login) as a password-protected ZIP.

Secrets portability decision (D8 follow-up): Trunk/SMTP/SIP passwords are
encrypted at rest with a key that lives only on the local host
(/data/.secret_key). A raw DB dump would only ever restore on that same
host. Instead, the entire config payload is re-encrypted with a key derived
from a password the user provides at export time (PBKDF2-HMAC-SHA256 ->
Fernet) - the backup ZIP is self-contained and portable to a fresh
instance, exactly what Phase B.4's "Fertig, wenn" criterion requires.

AdminUser is deliberately excluded: restoring a backup must not silently
change (or lock the admin out of) the login on the host being restored to.
"""

import base64
import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from zipfile import ZipFile, ZIP_DEFLATED

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import (
    Extension,
    Holiday,
    IVRMenu,
    OutboundRule,
    ProvisionedDevice,
    ProvisioningTemplate,
    RingGroup,
    Route,
    SmtpSettings,
    TimeCondition,
    Trunk,
    VoicemailSettings,
)
from backend.regeneration import run_regeneration_steps
from backend.routers.extensions import _regenerate_extensions_conf, _regenerate_voicemail_conf
from backend.routers.settings import regenerate_mail_configs
from backend.routers.time_conditions import _regenerate_routing_conf
from backend.routers.trunk import _regenerate_trunk_conf
from backend import ami

router = APIRouter()

BACKUP_FORMAT_VERSION = 1
_VERIFICATION_PLAINTEXT = b"ha-phone-backup-v1"
_PBKDF2_ITERATIONS = 480_000  # OWASP-recommended floor for PBKDF2-HMAC-SHA256

# Parents first (insert order); reversed for delete order (children first) so
# nothing is ever left referencing a row that was already wiped.
_MODELS_IN_DEPENDENCY_ORDER: list[type] = [
    Extension,
    ProvisioningTemplate,
    Trunk,
    SmtpSettings,
    RingGroup,
    IVRMenu,
    OutboundRule,
    Route,
    TimeCondition,
    VoicemailSettings,
    ProvisionedDevice,
    Holiday,
]


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def _collect_export_data(session: Session) -> dict[str, list[dict[str, Any]]]:
    data: dict[str, list[dict[str, Any]]] = {}
    template_names_by_id = {t.id: t.name for t in session.exec(select(ProvisioningTemplate)).all()}

    for model in _MODELS_IN_DEPENDENCY_ORDER:
        rows = session.exec(select(model)).all()
        if model is ProvisioningTemplate:
            # Builtins are reseeded on boot (seed_builtin_templates) - only the
            # user's own custom templates need to travel with the backup. Their
            # id is dropped (see restore) since builtins already occupy low ids
            # on a fresh instance before any restore runs.
            rows = [r for r in rows if not r.builtin]
            dumped = []
            for r in rows:
                d = r.model_dump()
                d.pop("id", None)
                dumped.append(d)
            data[model.__tablename__] = dumped
            continue
        if model is ProvisionedDevice:
            # template_id is host-specific (see above) - resolve it to the
            # template's NAME instead, which restore can look up on the
            # target host regardless of what id it landed on there.
            dumped = []
            for r in rows:
                d = r.model_dump()
                d["template_name"] = template_names_by_id.get(r.template_id, "")
                dumped.append(d)
            data[model.__tablename__] = dumped
            continue
        data[model.__tablename__] = [row.model_dump() for row in rows]
    return data


@router.post("/backup/export")
def export_backup(password: str = Form(...), session: Session = Depends(get_session)):
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Backup password must be at least 8 characters")

    salt = Fernet.generate_key()[:16]  # 16 random bytes, reusing Fernet's CSPRNG
    key = _derive_key(password, salt)
    fernet = Fernet(key)

    export_data = _collect_export_data(session)
    encrypted_payload = fernet.encrypt(json.dumps(export_data).encode())
    verification = fernet.encrypt(_VERIFICATION_PLAINTEXT)

    meta = {
        "format_version": BACKUP_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "salt": base64.b64encode(salt).decode(),
        "verification": verification.decode(),
        "kdf_iterations": _PBKDF2_ITERATIONS,
    }

    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        zf.writestr("meta.json", json.dumps(meta, indent=2))
        zf.writestr("data.enc", encrypted_payload)
    buf.seek(0)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="ha-phone-backup-{stamp}.zip"'},
    )


def _decrypt_backup(zip_bytes: bytes, password: str) -> dict[str, list[dict[str, Any]]]:
    try:
        with ZipFile(BytesIO(zip_bytes)) as zf:
            meta = json.loads(zf.read("meta.json"))
            encrypted_payload = zf.read("data.enc")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Not a valid HA-Phone backup file: {exc}")

    if meta.get("format_version") != BACKUP_FORMAT_VERSION:
        raise HTTPException(status_code=422, detail="Unsupported backup format version")

    salt = base64.b64decode(meta["salt"])
    key = _derive_key(password, salt)
    fernet = Fernet(key)

    try:
        if fernet.decrypt(meta["verification"].encode()) != _VERIFICATION_PLAINTEXT:
            raise InvalidToken()
    except InvalidToken:
        raise HTTPException(status_code=422, detail="Wrong backup password")

    try:
        return json.loads(fernet.decrypt(encrypted_payload))
    except InvalidToken:
        raise HTTPException(status_code=422, detail="Wrong backup password")


@router.post("/backup/import")
async def import_backup(
    file: UploadFile = File(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    zip_bytes = await file.read()
    export_data = _decrypt_backup(zip_bytes, password)

    # Wipe children-first, then re-insert parents-first, so a partially
    # restored DB never has a row pointing at something that doesn't exist
    # yet (even though SQLite here doesn't enforce FKs, staying consistent
    # avoids a confusing intermediate state if restore fails halfway).
    for model in reversed(_MODELS_IN_DEPENDENCY_ORDER):
        for row in session.exec(select(model)).all():
            if model is ProvisioningTemplate and row.builtin:
                continue  # keep builtins; they aren't part of the export either
            session.delete(row)
    session.commit()

    for model in _MODELS_IN_DEPENDENCY_ORDER:
        rows = export_data.get(model.__tablename__, [])
        if model is ProvisionedDevice:
            continue  # inserted after templates so template_name can be resolved
        for row_data in rows:
            row_data = dict(row_data)
            if model is ProvisioningTemplate:
                row_data.pop("id", None)  # let the DB assign a fresh id (avoids colliding with re-seeded builtins)
            session.add(model(**row_data))
    session.commit()

    template_id_by_name = {t.name: t.id for t in session.exec(select(ProvisioningTemplate)).all()}
    for row_data in export_data.get(ProvisionedDevice.__tablename__, []):
        row_data = dict(row_data)
        template_name = row_data.pop("template_name", "")
        row_data["template_id"] = template_id_by_name.get(template_name, 0)
        session.add(ProvisionedDevice(**row_data))
    session.commit()

    def _regen_trunk():
        trunk = session.exec(select(Trunk)).first()
        if trunk is not None:
            _regenerate_trunk_conf(trunk)
        else:
            return {"skipped": True, "message": "Kein Trunk im Backup enthalten"}

    summary = run_regeneration_steps(
        "backup.import",
        [
            ("extensions", lambda: _regenerate_extensions_conf(session)),
            ("voicemail", lambda: _regenerate_voicemail_conf(session)),
            ("routing", lambda: _regenerate_routing_conf(session)),
            ("mail", lambda: regenerate_mail_configs(session)),
            ("trunk", _regen_trunk),
        ],
    )
    await ami.ami_reload_pjsip()
    await ami.ami_reload_voicemail()
    await ami.ami_reload_dialplan()

    counts = {name: len(rows) for name, rows in export_data.items()}
    return {"ok": True, "restored": counts, "regeneration": summary}
