# 04 — Plasma view: note-reactive rendering

**What to build:** `--view plasma` renders a note-reactive visualization instead of the Dashboard. Each Active Note (a note currently sounding, derived by cross-referencing a Track's note data against the current Position) flashes: positioned by pitch, colored per-Track, intensity from velocity, lit for the note's actual duration then a short fixed fade after note-off. Renders in truecolor when the terminal supports it, falling back to 256-color otherwise.

**Blocked by:** 01, 02

**Status:** ready-for-agent

- [x] `--view plasma` is accepted and selects the Plasma view; `--view dashboard` (or omitting the flag) still selects Dashboard
- [x] Plasma fetches `project` itself (independent of the shared polling layer, which stays free of Track/note concerns) to obtain Track/note data
- [x] Active Note derivation: a note is active when the current Position (from the shared poller) falls within `[start_tick, start_tick + duration)` for that note, including correct behavior across a Loop boundary wraparound
- [x] Each Active Note's flash is positioned spatially by pitch (consistent mapping across the pitch range)
- [x] Each Active Note's flash is colored by its Track, with one stable hue per Track for the session, assigned in Track order
- [x] Each Active Note's flash intensity/brightness reflects its velocity
- [x] A flash stays lit for the note's actual duration (converted from ticks to wall-clock time via current bpm) and then fades over a short fixed decay (~100ms) after note-off — not a uniform fixed-length blip
- [x] Plasma uses 24-bit truecolor when the terminal advertises support, and falls back to a 256-color approximation otherwise, without erroring or blocking startup
- [x] Plasma's own `project`/track fetch surfaces the same disconnected-state handling as ticket 02 (doesn't crash if the Engine is unreachable when Plasma tries to fetch track data)
- [x] No full track/note detail is rendered (no piano-roll or track-editor view) — only the derived Active Note signal drives rendering
- [x] Test: using the fake-Engine harness, configure canned `project`/`get_position` responses describing known notes at known positions, drive the app via `Pilot`, and assert the expected Active Notes are rendered (position/color/intensity) at the right times, including a case spanning a Loop-boundary wraparound
