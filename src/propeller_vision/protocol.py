"""One-shot request/response client for the propeller-engine JSON socket protocol.

Each command opens a new connection, writes one newline-terminated JSON
object, reads one JSON response line, then disconnects -- there is no
persistent session or subscribe/push mechanism.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

JsonDict = dict[str, Any]


class EngineClient:
    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path

    async def status(self) -> JsonDict:
        return await self._request({"command": "status"})

    async def project(self) -> JsonDict:
        return await self._request({"command": "project"})

    async def get_position(self) -> JsonDict:
        return await self._request({"type": "get_position"})

    async def _request(self, payload: JsonDict) -> JsonDict:
        reader, writer = await asyncio.open_unix_connection(self.socket_path)
        try:
            writer.write(json.dumps(payload).encode() + b"\n")
            await writer.drain()
            line = await reader.readline()
            result: JsonDict = json.loads(line)
            return result
        finally:
            writer.close()
            await writer.wait_closed()
