"""Central 10-99 numbering-space service (Roadmap Phase A.1, resolves D5).

Extensions, ring groups, and IVR menus all share one internal dial-number
space (10-99). Before this module existed, `ring_groups.py` and `ivr.py` each
carried their own near-identical cross-table collision check, and
`extensions.py` had none at all — an extension could silently be created
with a number already used by a ring group or IVR menu. This is the single
place that answers "is number X in 10-99 free, and if not, who owns it".
"""

from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.models import Extension, IVRMenu, RingGroup

NUMBER_MIN = 10
NUMBER_MAX = 99

_OWNER_LABELS = {
    "extension": "an extension",
    "ring_group": "a ring group",
    "ivr": "an IVR menu",
}


def find_number_owner(
    session: Session,
    number: int,
    exclude_kind: Optional[str] = None,
    exclude_id: Optional[int] = None,
) -> Optional[str]:
    """Return a human-readable label for whoever already owns `number` across
    Extension/RingGroup/IVRMenu, or None if it's free. `exclude_kind` +
    `exclude_id` let a caller ignore its own record when validating an update."""
    extension = session.exec(select(Extension).where(Extension.number == number)).first()
    if extension and not (exclude_kind == "extension" and extension.id == exclude_id):
        return _OWNER_LABELS["extension"]

    ring_group = session.exec(select(RingGroup).where(RingGroup.number == number)).first()
    if ring_group and not (exclude_kind == "ring_group" and ring_group.id == exclude_id):
        return _OWNER_LABELS["ring_group"]

    ivr = session.exec(select(IVRMenu).where(IVRMenu.number == number)).first()
    if ivr and not (exclude_kind == "ivr" and ivr.id == exclude_id):
        return _OWNER_LABELS["ivr"]

    return None


def validate_number(
    session: Session,
    number: int,
    kind: str,
    exclude_id: Optional[int] = None,
) -> None:
    """Raise HTTPException(422) if `number` is outside 10-99 or already used by
    another extension/ring group/IVR menu. `kind` is the type being
    validated ("extension" | "ring_group" | "ivr") so its own existing record
    is excluded during an update."""
    if number < NUMBER_MIN or number > NUMBER_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"number must be between {NUMBER_MIN} and {NUMBER_MAX}",
        )
    owner = find_number_owner(session, number, exclude_kind=kind, exclude_id=exclude_id)
    if owner:
        raise HTTPException(
            status_code=422,
            detail=f"number {number} is already used by {owner}",
        )
