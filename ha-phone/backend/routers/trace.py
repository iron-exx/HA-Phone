import asyncio
import signal
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

CAPTURE_FILE = Path("/tmp/haphone-capture.pcap")

_proc: asyncio.subprocess.Process | None = None


@router.post("/trace/start")
async def start_trace():
    global _proc
    if _proc is not None and _proc.returncode is None:
        return {"running": True, "message": "already_running"}

    # Capture SIP signalling + RTP audio
    _proc = await asyncio.create_subprocess_exec(
        "tcpdump", "-i", "any", "-w", str(CAPTURE_FILE),
        "port 5060 or port 5061 or (udp and portrange 10000-20000)",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return {"running": True}


@router.post("/trace/stop")
async def stop_trace():
    global _proc
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

    file_exists = CAPTURE_FILE.exists()
    size = CAPTURE_FILE.stat().st_size if file_exists else 0
    return {
        "running": False,
        "file_ready": file_exists and size > 0,
        "size_bytes": size,
    }


@router.get("/trace/status")
async def trace_status():
    running = _proc is not None and _proc.returncode is None
    file_exists = CAPTURE_FILE.exists()
    size = CAPTURE_FILE.stat().st_size if file_exists else 0
    return {
        "running": running,
        "file_ready": not running and file_exists and size > 0,
        "size_bytes": size,
    }


@router.get("/trace/download")
async def download_trace():
    if not CAPTURE_FILE.exists() or CAPTURE_FILE.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="No capture file available")
    return FileResponse(
        str(CAPTURE_FILE),
        media_type="application/vnd.tcpdump.pcap",
        filename="haphone-capture.pcap",
    )


@router.delete("/trace/file")
async def delete_trace():
    if CAPTURE_FILE.exists():
        CAPTURE_FILE.unlink()
    return {"deleted": True}
