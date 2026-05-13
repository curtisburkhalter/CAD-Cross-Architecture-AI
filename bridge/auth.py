"""
API key authentication middleware.
Validates the Authorization header against configured keys.
"""

import logging

from fastapi import Request, HTTPException

logger = logging.getLogger("zgx-bridge.auth")


class APIKeyAuth:
    def __init__(self, valid_keys: list[str]):
        self._valid_keys = set(valid_keys)

    async def __call__(self, request: Request) -> None:
        # Skip auth for health, metrics, widget static files
        path = request.url.path
        if path in ("/api/health", "/api/metrics") or path.startswith("/widget"):
            return

        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            key = auth_header[7:].strip()
        else:
            key = auth_header.strip()

        if not key or key not in self._valid_keys:
            logger.warning("Invalid API key from %s on %s", request.client.host, path)
            raise HTTPException(status_code=401, detail="Invalid or missing API key.")
