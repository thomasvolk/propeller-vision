"""The Space View: a vertical-scrolling space visualization that Active Notes drive.

Reuses Plasma's Active Note machinery (`active_notes`, `ProjectPoller`,
`clock_is_running`, `music_rate`) rather than duplicating it -- deriving
"currently sounding notes" from Track/Position data is a Plasma-View concept
per ADR-0004, and this view needs the exact same derived signal.

Each Track gets its own vertical lane. The moment one of its notes becomes
Active, a marker spawns at the top of that lane and scrolls downward at a
tempo-driven rate, independent of how long the note itself keeps sounding --
like a fired projectile, it keeps travelling until it scrolls past the
bottom row, at which point it's dropped (a later re-trigger, e.g. the loop
repeating, spawns a fresh marker). The same trigger also spawns an alien
ship in that lane, descending alongside the marker on a tempo-paced sine
wobble. A single ship sits at a fixed row near the bottom; its horizontal
position tracks the pitch of the highest-pitched note currently Active
across all Tracks, returning to center when nothing is sounding. That same
note-Active trigger fires a shot straight up from the ship's current
column; a shot that reaches a marker or alien ship destroys it.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from rich.style import Style
from rich.text import Text
from textual.widgets import Static

from propeller_vision.dashboard import WAITING_FOR_ENGINE_MESSAGE
from propeller_vision.plasma import (
    PITCH_RANGE,
    ActiveNote,
    NoteKey,
    ProjectPoller,
    active_notes,
    clock_is_running,
    music_rate,
)
from propeller_vision.poller import Poller
from propeller_vision.protocol import JsonDict

# Animation frame cadence -- matches Plasma's, decoupled from the poll interval.
FRAME_INTERVAL = 1 / 20

# How many rows a marker travels per beat of music-time -- the scroll's
# tempo-driven pace, analogous to Plasma's flow speed.
SCROLL_ROWS_PER_BEAT = 6.0

# A small multi-cell sprite (nose, cockpit, wings) rather than a single glyph,
# so the ship reads as a ship rather than a dot -- rows are bottom-anchored
# and horizontally centered on the ship's tracked column.
SHIP_SPRITE = (
    "  ▲  ",
    " ▲■▲ ",
    "▲■■■▲",
)
SHIP_STYLE = Style(color="bright_cyan", bold=True)
MARKER_STYLE = Style(color="grey50", bold=True)
ALIEN_STYLE = Style(color="bright_magenta", bold=True)
SHOT_STYLE = Style(color="bright_yellow", bold=True)

ALIEN_GLYPH = "✦"
SHOT_GLYPH = "|"

# The alien ships' side-to-side wobble as they descend: amplitude is a
# fraction of their lane's width (so the wave reads as motion within the
# lane, not a drift into a neighbor's), and its period is counted in beats
# like everything else in this view, so it stays tempo-paced.
ALIEN_WAVE_LANE_FRACTION = 0.3
ALIEN_WAVE_BEATS_PER_CYCLE = 4.0


@dataclass(frozen=True)
class Marker:
    track_index: int
    velocity: int
    spawned_at: float


@dataclass(frozen=True)
class Alien:
    track_index: int
    spawned_at: float


@dataclass(frozen=True)
class Shot:
    column: int
    spawned_at: float
    spawn_row: float


def track_count(project: JsonDict | None) -> int:
    if project is None:
        return 0
    current = project.get("current")
    if not current:
        return 0
    return len(current.get("tracks", []))


def lane_bounds(track_index: int, lanes: int, cols: int) -> tuple[int, int]:
    """The [start, end) column range for a Track's lane, splitting the width evenly."""
    lanes = max(lanes, 1)
    start = round(track_index * cols / lanes)
    end = round((track_index + 1) * cols / lanes)
    return start, end


def marker_column(track_index: int, lanes: int, cols: int) -> int:
    """A Track's lane, collapsed to the single column its markers render in."""
    start, end = lane_bounds(track_index, lanes, cols)
    return min(max((start + end) // 2, 0), cols - 1)


def marker_glyph(velocity: int) -> str:
    """Louder notes render as visually bigger markers."""
    if velocity >= 96:
        return "@"
    if velocity >= 48:
        return "o"
    return "."


def marker_row(marker: Marker, music_time: float) -> float:
    return (music_time - marker.spawned_at) * SCROLL_ROWS_PER_BEAT


def update_markers(
    previous: dict[NoteKey, Marker],
    active: dict[NoteKey, ActiveNote],
    music_time: float,
    lines: int,
) -> dict[NoteKey, Marker]:
    kept = {key: marker for key, marker in previous.items() if marker_row(marker, music_time) < lines}
    for key, note in active.items():
        if key not in kept:
            kept[key] = Marker(track_index=note.track_index, velocity=note.velocity, spawned_at=music_time)
    return kept


def alien_row(alien: Alien, music_time: float) -> float:
    return (music_time - alien.spawned_at) * SCROLL_ROWS_PER_BEAT


def alien_column(alien: Alien, music_time: float, lanes: int, cols: int) -> int:
    """Alien ships wobble side to side around their lane's center as they
    descend, the wave paced in beats like everything else in this view."""
    start, end = lane_bounds(alien.track_index, lanes, cols)
    center = (start + end) / 2
    amplitude = (end - start) * ALIEN_WAVE_LANE_FRACTION
    phase = (music_time - alien.spawned_at) / ALIEN_WAVE_BEATS_PER_CYCLE * math.tau
    col = round(center + amplitude * math.sin(phase))
    return min(max(col, 0), cols - 1)


def update_aliens(
    previous: dict[NoteKey, Alien],
    active: dict[NoteKey, ActiveNote],
    music_time: float,
    lines: int,
) -> dict[NoteKey, Alien]:
    kept = {key: alien for key, alien in previous.items() if alien_row(alien, music_time) < lines}
    for key, note in active.items():
        if key not in kept:
            kept[key] = Alien(track_index=note.track_index, spawned_at=music_time)
    return kept


def shot_row(shot: Shot, music_time: float) -> float:
    return shot.spawn_row - (music_time - shot.spawned_at) * SCROLL_ROWS_PER_BEAT


def update_shots(
    previous: dict[NoteKey, Shot],
    active: dict[NoteKey, ActiveNote],
    music_time: float,
    ship_col: int,
    spawn_row: float,
) -> dict[NoteKey, Shot]:
    """The ship fires on the same note-Active trigger that spawns a marker --
    one shot per triggering note, from wherever the ship (pitch-driven) sits
    at that moment."""
    kept = {key: shot for key, shot in previous.items() if shot_row(shot, music_time) >= 0}
    for key in active:
        if key not in kept:
            kept[key] = Shot(column=ship_col, spawned_at=music_time, spawn_row=spawn_row)
    return kept


def resolve_hits(
    shots: dict[NoteKey, Shot],
    markers: dict[NoteKey, Marker],
    aliens: dict[NoteKey, Alien],
    music_time: float,
    lanes: int,
    cols: int,
) -> tuple[dict[NoteKey, Shot], dict[NoteKey, Marker], dict[NoteKey, Alien]]:
    """A shot destroys the first marker or alien ship it shares a cell with;
    both the shot and its target are consumed, so one shot can't chain-clear
    a column in a single frame."""
    hit_shots: set[NoteKey] = set()
    hit_markers: set[NoteKey] = set()
    hit_aliens: set[NoteKey] = set()

    marker_positions = {
        key: (int(marker_row(marker, music_time)), marker_column(marker.track_index, lanes, cols))
        for key, marker in markers.items()
    }
    alien_positions = {
        key: (int(alien_row(alien, music_time)), alien_column(alien, music_time, lanes, cols))
        for key, alien in aliens.items()
    }

    for shot_key, shot in shots.items():
        shot_pos = (int(shot_row(shot, music_time)), shot.column)
        hit_marker = next(
            (key for key, pos in marker_positions.items() if key not in hit_markers and pos == shot_pos), None
        )
        if hit_marker is not None:
            hit_shots.add(shot_key)
            hit_markers.add(hit_marker)
            continue
        hit_alien = next(
            (key for key, pos in alien_positions.items() if key not in hit_aliens and pos == shot_pos), None
        )
        if hit_alien is not None:
            hit_shots.add(shot_key)
            hit_aliens.add(hit_alien)

    remaining_shots = {key: shot for key, shot in shots.items() if key not in hit_shots}
    remaining_markers = {key: marker for key, marker in markers.items() if key not in hit_markers}
    remaining_aliens = {key: alien for key, alien in aliens.items() if key not in hit_aliens}
    return remaining_shots, remaining_markers, remaining_aliens


def ship_column(active: dict[NoteKey, ActiveNote], cols: int) -> int:
    """The ship follows the highest-pitched currently Active Note across all
    Tracks, and rests at center when nothing is sounding."""
    if not active:
        return cols // 2
    highest = max(active.values(), key=lambda note: note.pitch)
    return round((highest.pitch / (PITCH_RANGE - 1)) * max(cols - 1, 0))


def draw_ship(
    grid: list[list[str]],
    styles: dict[tuple[int, int], Style],
    ship_col: int,
    cols: int,
    lines: int,
) -> None:
    """Stamps the SHIP_SPRITE onto the grid, bottom-anchored and centered on
    ship_col; cells the sprite's rows/columns push off-grid are clipped."""
    height = len(SHIP_SPRITE)
    width = len(SHIP_SPRITE[0])
    top_row = lines - height
    left_col = ship_col - width // 2
    for dy, sprite_row in enumerate(SHIP_SPRITE):
        row = top_row + dy
        if row < 0 or row >= lines:
            continue
        for dx, ch in enumerate(sprite_row):
            if ch == " ":
                continue
            col = left_col + dx
            if 0 <= col < cols:
                grid[row][col] = ch
                styles[(row, col)] = SHIP_STYLE


def render_space_frame(
    cols: int,
    lines: int,
    markers: dict[NoteKey, Marker],
    aliens: dict[NoteKey, Alien],
    shots: dict[NoteKey, Shot],
    music_time: float,
    ship_col: int,
    lanes: int,
) -> Text:
    grid: list[list[str]] = [[" "] * cols for _ in range(lines)]
    styles: dict[tuple[int, int], Style] = {}

    for marker in markers.values():
        row = int(marker_row(marker, music_time))
        if row < 0 or row >= lines:
            continue
        col = marker_column(marker.track_index, lanes, cols)
        grid[row][col] = marker_glyph(marker.velocity)
        styles[(row, col)] = MARKER_STYLE

    for alien in aliens.values():
        row = int(alien_row(alien, music_time))
        if row < 0 or row >= lines:
            continue
        col = alien_column(alien, music_time, lanes, cols)
        grid[row][col] = ALIEN_GLYPH
        styles[(row, col)] = ALIEN_STYLE

    for shot in shots.values():
        row = int(shot_row(shot, music_time))
        if row < 0 or row >= lines:
            continue
        col = min(max(shot.column, 0), cols - 1)
        grid[row][col] = SHOT_GLYPH
        styles[(row, col)] = SHOT_STYLE

    draw_ship(grid, styles, ship_col, cols, lines)

    text = Text()
    for y in range(lines):
        for x in range(cols):
            style = styles.get((y, x))
            text.append(grid[y][x], style=style) if style is not None else text.append(grid[y][x])
        if y < lines - 1:
            text.append("\n")
    return text


class SpaceView(Static):
    DEFAULT_CSS = """
    SpaceView {
        width: 100%;
        height: 100%;
    }
    """

    def __init__(self, scroll_speed: float = 1.0) -> None:
        super().__init__(WAITING_FOR_ENGINE_MESSAGE)
        self._scroll_speed = scroll_speed
        self._markers: dict[NoteKey, Marker] = {}
        self._aliens: dict[NoteKey, Alien] = {}
        self._shots: dict[NoteKey, Shot] = {}
        self._active: dict[NoteKey, ActiveNote] = {}
        self._lanes = 1
        self._connected = False
        self._running = False
        self._bpm: float | None = None
        self._music_time = 0.0
        self._last_tick_at: float | None = None
        self._has_rendered_frame = False

    def on_mount(self) -> None:
        self.set_interval(FRAME_INTERVAL, self._draw_frame)

    def update_from(self, poller: Poller, project_poller: ProjectPoller) -> None:
        if not poller.connected or not project_poller.connected:
            self._connected = False
            self._active = {}
            return
        self._connected = True
        self._running = clock_is_running(poller.status)
        self._bpm = poller.status.get("bpm") if poller.status else None
        self._lanes = max(track_count(project_poller.project), 1)
        self._active = active_notes(project_poller.project, poller.position)

    def _advance_music_time(self, now: float) -> None:
        # Reset the tick reference on every call so a pause never counts
        # toward the next dt -- resuming continues the scroll from where it
        # froze instead of jumping forward by however long it was paused.
        if self._running:
            rate = music_rate(self._bpm)
            if rate is not None and self._last_tick_at is not None:
                self._music_time += (now - self._last_tick_at) * rate * self._scroll_speed
        self._last_tick_at = now

    def _draw_frame(self) -> None:
        now = time.monotonic()
        if not self._connected:
            self.update(WAITING_FOR_ENGINE_MESSAGE, layout=False)
            self._has_rendered_frame = False
            self._last_tick_at = None
            return
        self._advance_music_time(now)
        # Freeze once at least one real frame is on screen; a fresh connection
        # that's paused from the start still needs its first frame drawn.
        if not self._running and self._has_rendered_frame:
            return
        cols, lines = self.size.width, self.size.height
        if cols <= 0 or lines <= 0:
            return
        self._markers = update_markers(self._markers, self._active, self._music_time, lines)
        self._aliens = update_aliens(self._aliens, self._active, self._music_time, lines)
        ship_col = ship_column(self._active, cols)
        spawn_row = float(lines - len(SHIP_SPRITE))
        self._shots = update_shots(self._shots, self._active, self._music_time, ship_col, spawn_row)
        self._shots, self._markers, self._aliens = resolve_hits(
            self._shots, self._markers, self._aliens, self._music_time, self._lanes, cols
        )
        frame = render_space_frame(
            cols, lines, self._markers, self._aliens, self._shots, self._music_time, ship_col, self._lanes
        )
        self.update(frame, layout=False)
        self._has_rendered_frame = True
