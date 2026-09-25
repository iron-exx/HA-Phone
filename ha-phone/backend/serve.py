"""Runs the FastAPI app on plain HTTP :80 (admin UI, older app versions) and, when the
TLS cert exists, on HTTPS :8443 for the app (cert pinned via backend.tls_pin).

One process, two uvicorn servers: only the HTTP server runs the lifespan, so the
AMI listeners and pollers start once.
"""
import asyncio
import logging
import os

import uvicorn

from backend import tls_pin

log = logging.getLogger("ha_phone.serve")


def _servers() -> list:
    http_port = int(os.environ.get("BPX_HTTP_PORT", "80"))
    http = uvicorn.Config("backend.main:app", host="0.0.0.0", port=http_port, log_level="info")
    servers = [uvicorn.Server(http)]
    if tls_pin.cert_path().is_file() and tls_pin.key_path().is_file():
        https = uvicorn.Config(
            "backend.main:app",
            host="0.0.0.0",
            port=int(os.environ.get("BPX_HTTPS_PORT", str(tls_pin.HTTPS_PORT))),
            log_level="info",
            lifespan="off",
            ssl_certfile=str(tls_pin.cert_path()),
            ssl_keyfile=str(tls_pin.key_path()),
        )
        servers.append(uvicorn.Server(https))
    else:
        log.warning("TLS cert missing, HTTPS API on :%s disabled", tls_pin.HTTPS_PORT)
    return servers


async def _optional(server: uvicorn.Server) -> None:
    """HTTPS is an extra: if it cannot start (port taken, bad cert), keep HTTP running."""
    try:
        await server.serve()
    except (SystemExit, OSError) as exc:
        log.error("HTTPS API on :%s failed: %r", server.config.port, exc)


async def _main() -> None:
    http, *extra = _servers()
    tasks = [asyncio.create_task(_optional(s)) for s in extra]
    try:
        await http.serve()
    finally:
        # HTTP runs the lifespan: when it stops (signal or failed startup), stop HTTPS too,
        # so s6 restarts the whole backend instead of leaving an HTTPS-only zombie.
        for s in extra:
            s.should_exit = True
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(_main())
