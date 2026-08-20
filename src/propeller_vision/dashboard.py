"""The Dashboard View: a Position playhead plus a status panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from propeller_vision.poller import Poller
from propeller_vision.protocol import JsonDict

PLAYHEAD_WIDTH = 40

# Shared across Views: what to show while the Engine is unreachable.
WAITING_FOR_ENGINE_MESSAGE = "Waiting for engine..."


def format_playhead(position: JsonDict | None) -> str:
    if position is None:
        return WAITING_FOR_ENGINE_MESSAGE
    tick = position.get("tick")
    duration = position.get("loop_duration")
    if tick is None or not duration:
        return "No project loaded"
    filled = max(0, min(PLAYHEAD_WIDTH, int(PLAYHEAD_WIDTH * tick / duration)))
    bar = "#" * filled + "." * (PLAYHEAD_WIDTH - filled)
    return f"[{bar}] {tick}/{duration}"


def format_status_panel(
    status: JsonDict | None, project: JsonDict | None, position: JsonDict | None = None
) -> str:
    if status is None:
        return WAITING_FOR_ENGINE_MESSAGE
    lines = [
        f"Mode: {status.get('mode', '?')}",
        f"BPM: {status.get('bpm', '?')}",
        f"Clock: {status.get('clock_state', '?')}",
    ]
    if status.get("mode") == "sync":
        lines.append(f"Sync: {status.get('sync_clock_state', '?')}")
    current = bool(project and project.get("current"))
    pending = bool(project and project.get("pending"))
    lines.append(f"Project: current={'yes' if current else 'no'} pending={'yes' if pending else 'no'}")
    loop_count = position.get("loop_count") if position else None
    if loop_count is not None:
        lines.append(f"Loop: {loop_count}")
    return "\n".join(lines)


class Dashboard(Vertical):
    def compose(self) -> ComposeResult:
        yield Static(format_playhead(None), id="playhead")
        yield Static(format_status_panel(None, None), id="status-panel")

    def update_from(self, poller: Poller) -> None:
        self.query_one("#playhead", Static).update(format_playhead(poller.position))
        self.query_one("#status-panel", Static).update(
            format_status_panel(poller.status, poller.project, poller.position)
        )
