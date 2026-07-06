from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)

StepFunc = Callable[[], Any]

STEP_LABELS = {
    "extensions": "Nebenstellen-Konfiguration",
    "voicemail": "Voicemail-Konfiguration",
    "routing": "Routing-Konfiguration",
    "mail": "Mail-Konfiguration",
    "trunk": "Trunk-Konfiguration",
}

STEP_ORDER = ["extensions", "voicemail", "routing", "mail", "trunk"]


def _data_dir() -> Path:
    data_dir = os.environ.get("BPX_DATA_DIR", "")
    return Path(data_dir) if data_dir else Path("/data")


def _status_path() -> Path:
    return _data_dir() / "asterisk" / "config_regeneration_status.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_status() -> dict[str, Any]:
    return {
        "ok": True,
        "source": None,
        "last_run_at": None,
        "last_failure_at": None,
        "steps": [],
    }


def skipped_regeneration(message: str) -> dict[str, Any]:
    return {"skipped": True, "message": message}


def get_regeneration_status() -> dict[str, Any]:
    path = _status_path()
    if not path.exists():
        return _default_status()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read config regeneration status: %s", exc)
        return {
            "ok": False,
            "source": "status.read",
            "last_run_at": _utc_now(),
            "last_failure_at": _utc_now(),
            "steps": [
                {
                    "name": "status",
                    "label": "Regenerierungsstatus",
                    "ok": False,
                    "skipped": False,
                    "updated_at": _utc_now(),
                    "message": f"{type(exc).__name__}: {exc}",
                }
            ],
        }


def _write_status(status: dict[str, Any]) -> None:
    path = _status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as tmp:
        json.dump(status, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    os.replace(tmp_path, path)


def _step_order(name: str) -> tuple[int, str]:
    try:
        return (STEP_ORDER.index(name), name)
    except ValueError:
        return (len(STEP_ORDER), name)


def _normalize_step_result(
    name: str,
    run_at: str,
    ok: bool,
    message: str,
    skipped: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "label": STEP_LABELS.get(name, name.replace("_", " ").title()),
        "ok": ok,
        "skipped": skipped,
        "updated_at": run_at,
        "message": message,
    }


def run_regeneration_steps(
    source: str,
    steps: Iterable[tuple[str, StepFunc]],
) -> dict[str, Any]:
    run_at = _utc_now()
    previous = get_regeneration_status()
    if previous.get("source") == "status.read":
        previous = _default_status()
    merged_steps = {
        step.get("name"): step
        for step in previous.get("steps", [])
        if isinstance(step, dict) and step.get("name")
    }

    for name, func in steps:
        try:
            result = func()
            skipped = False
            message = "Aktualisiert"
            if isinstance(result, dict):
                skipped = bool(result.get("skipped"))
                message = str(result.get("message") or ("Uebersprungen" if skipped else message))
            elif isinstance(result, str) and result.strip():
                message = result
            elif result is False:
                message = "Keine Aenderung noetig"
            merged_steps[name] = _normalize_step_result(
                name=name,
                run_at=run_at,
                ok=True,
                message=message,
                skipped=skipped,
            )
        except Exception as exc:
            logger.exception(
                "Config regeneration step '%s' failed during %s",
                name,
                source,
            )
            merged_steps[name] = _normalize_step_result(
                name=name,
                run_at=run_at,
                ok=False,
                message=f"{type(exc).__name__}: {exc}",
            )

    ordered_steps = sorted(merged_steps.values(), key=lambda step: _step_order(step["name"]))
    failed_steps = [step for step in ordered_steps if not step.get("ok")]
    status = {
        "ok": not failed_steps,
        "source": source,
        "last_run_at": run_at,
        "last_failure_at": max((step["updated_at"] for step in failed_steps), default=None),
        "steps": ordered_steps,
    }
    _write_status(status)
    return status


def run_single_regeneration_step(
    source: str,
    step_name: str,
    func: StepFunc,
) -> dict[str, Any]:
    return run_regeneration_steps(source, [(step_name, func)])


def step_succeeded(status: dict[str, Any], name: str) -> bool:
    for step in status.get("steps", []):
        if step.get("name") == name:
            return bool(step.get("ok"))
    return False
