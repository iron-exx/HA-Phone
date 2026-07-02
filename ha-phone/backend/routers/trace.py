import asyncio
import signal
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

CAPTURE_FILE = Path("/tmp/haphone-capture.pcap")

_proc: asyncio.subprocess.Process | None = None
# Epoch seconds when the current capture started. Returned in status so the UI can
# derive elapsed time from a fixed anchor — a client-side counter resets to 0 on every
# tab switch / remount even though the capture keeps running.
_started_at: float | None = None


@router.post("/trace/start")
async def start_trace():
    global _proc, _started_at
    if _proc is not None and _proc.returncode is None:
        return {"running": True, "message": "already_running", "started_at": _started_at}

    # Capture SIP signalling + RTP audio
    _proc = await asyncio.create_subprocess_exec(
        "tcpdump", "-i", "any", "-w", str(CAPTURE_FILE),
        "port 5060 or port 5061 or (udp and portrange 10000-20000)",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    _started_at = time.time()
    return {"running": True, "started_at": _started_at}


@router.post("/trace/stop")
async def stop_trace():
    global _proc, _started_at
    if _proc is not None and _proc.returncode is None:
        try:
            _proc.send_signal(signal.SIGINT)
            await asyncio.wait_for(_proc.wait(), timeout=5.0)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                _proc.kill()
                await _proc.wait()
            except ProcessLookupError:
                pass

    _started_at = None
    file_exists = CAPTURE_FILE.exists()
    size = CAPTURE_FILE.stat().st_size if file_exists else 0
    return {
        "running": False,
        "file_ready": file_exists and size > 0,
        "size_bytes": size,
        "started_at": None,
    }


@router.get("/trace/status")
async def trace_status():
    running = _proc is not None and _proc.returncode is None
    file_exists = CAPTURE_FILE.exists()
    stat = CAPTURE_FILE.stat() if file_exists else None
    size = stat.st_size if stat else 0
    return {
        "running": running,
        "file_ready": not running and file_exists and size > 0,
        "size_bytes": size,
        "started_at": _started_at if running else None,
        # mtime of the capture = when it finished recording. Lets the UI label each
        # trace with its time so multiple captures aren't confused.
        "file_mtime": stat.st_mtime if stat else None,
    }


@router.get("/trace/download")
async def download_trace():
    if not CAPTURE_FILE.exists() or CAPTURE_FILE.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="No capture file available")
    # Timestamped filename so downloaded traces stay distinct on disk.
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(CAPTURE_FILE.stat().st_mtime))
    return FileResponse(
        str(CAPTURE_FILE),
        media_type="application/vnd.tcpdump.pcap",
        filename=f"haphone-capture-{stamp}.pcap",
    )


@router.delete("/trace/file")
async def delete_trace():
    if CAPTURE_FILE.exists():
        CAPTURE_FILE.unlink()
    return {"deleted": True}
