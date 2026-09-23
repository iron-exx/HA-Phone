"""Where app_voicemail keeps a mailbox: <astspooldir>/voicemail/<context>/<mailbox>.
astspooldir is /data/voicemail (rootfs/etc/asterisk/asterisk.conf)."""
import os
from pathlib import Path


def data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def mailbox_dir(ext_number: int, context: str = "default") -> Path:
    return data_dir() / "voicemail" / "voicemail" / context / str(ext_number)
