"""A fake propeller-engine: a Unix-socket test server implementing the
status/project/get_position protocol subset with configurable canned
responses. Tests point propeller-vision at this instead of a real engine.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


class FakeEngine:
    def __init__(self) -> None:
        self.responses: dict[str, JsonDict] = {}
        self.request_counts: dict[str, int] = {}
        self._server: asyncio.Server | None = None
        self.socket_path: Path | None = None

    def set_response(self, key: str, response: JsonDict) -> None:
        """key is 'status', 'project', or 'get_position'."""
        self.responses[key] = response

    async def start(self, socket_path: Path) -> None:
        self.socket_path = socket_path
        self._server = await asyncio.start_unix_server(self._handle, path=str(socket_path))

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        if self.socket_path is not None and self.socket_path.exists():
            self.socket_path.unlink()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        line = await reader.readline()
        request = json.loads(line)
        key = request.get("command") or request.get("type")
        self.request_counts[key] = self.request_counts.get(key, 0) + 1
        response = self.responses.get(key, {"status": "error", "error": "unknown_command"})
        writer.write(json.dumps(response).encode() + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
