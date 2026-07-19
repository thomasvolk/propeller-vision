---
status: superseded by ADR-0004
---

# Track/note-level detail is out of scope for v1

The engine's `project` query returns full track data (instrument, MIDI channel, notes, pitch-bends), which could support a piano-roll style view. We decided propeller-vision v1 only surfaces Project-level header info (e.g. whether a project is current/pending) in the dashboard, not per-track or per-note detail. Rendering note-level data is a materially bigger feature (a different kind of view entirely) and isn't needed to satisfy the core goal of visualizing loop position and engine state. This can be added later without changing the read-only monitor architecture.

See ADR-0004: the Plasma view brought "currently active notes" into scope, refining this decision.
