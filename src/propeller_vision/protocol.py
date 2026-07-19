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


class EngineUnavailable(Exception):
    """The Engine couldn't be reached, or didn't answer the protocol correctly."""


class EngineClient:
    def __init__(self, socket_path: str, timeout: float = 0.5) -> None:
        self.socket_path = socket_path
        self.timeout = timeout

    async def status(self) -> JsonDict:
        return await self._request({"command": "status"})

    async def project(self) -> JsonDict:
        return await self._request({"command": "project"})

    async def get_position(self) -> JsonDict:
        return await self._request({"type": "get_position"})

    async def _request(self, payload: JsonDict) -> JsonDict:
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            writer.write(json.dumps(payload).encode() + b"\n")
            await writer.drain()
            # Only the read is time-bounded: connect and write either
            # succeed near-instantly or fail outright, but a connected-but-
            # silent Engine could otherwise block here forever. asyncio.timeout
            # (not wait_for) composes safely with the poller's own
            # task.cancel() -- wait_for's nested-cancellation handling can
            # hang when the outer task is cancelled mid-wait.
            try:
                async with asyncio.timeout(self.timeout):
                    line = await reader.readline()
            except TimeoutError as exc:
                raise EngineUnavailable("timed out waiting for a response") from exc
            if not line:
                raise EngineUnavailable("connection closed before a response was received")
            try:
                result: JsonDict = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EngineUnavailable(f"invalid response: {exc}") from exc
            return result
        except OSError as exc:
            raise EngineUnavailable(str(exc)) from exc
        finally:
            if writer is not None:
                writer.close()
                # Best-effort: don't let a socket stuck mid-teardown block
                # the caller (or its own cancellation) indefinitely.
                try:
                    async with asyncio.timeout(1.0):
                        await writer.wait_closed()
                except (OSError, TimeoutError):
                    pass
