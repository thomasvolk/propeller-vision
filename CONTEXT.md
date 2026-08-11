# Propeller Vision

A read-only console monitor that observes a running propeller-engine and visualizes the state of its playback Loop.

## Language

**Engine**:
The propeller-engine process that propeller-vision connects to over its socket protocol and observes. propeller-vision never sends it control/mutation commands, only queries.

**Loop**:
The repeating unit of playback the Engine plays. Has a duration (in ticks) and a current Position within that duration.
_Avoid_: pattern, cycle

**Position**:
The current tick location within the Loop, as reported by the Engine's `get_position` query. Rendered in the dashboard as the playhead.
_Avoid_: tick (use Position for the concept; "tick" is the unit)

**Project**:
The set of musical data the Engine plays: a header (BPM, loop duration) plus Tracks. Has a Current (active) version and optionally a Pending (staged) version awaiting the next loop boundary.

**Track**:
Part of a Project: a single instrument line with its notes. Not rendered directly (no piano-roll/track-editor view), but its note data is used to derive Active Notes for the Plasma and Space Views.

**Mode**:
The Engine's operating mode: `standalone`, `clock`, or `sync`. Affects what state fields are meaningful (e.g. `sync_clock_state` only applies in `sync` mode).

**View**:
One of the selectable ways propeller-vision renders Engine state: Dashboard, Plasma, or Space. Chosen via a CLI flag at startup; fixed for the session (no runtime switching).

**Dashboard**:
The default View: a Position playhead plus a status panel (Mode, bpm, current/pending Project header).

**Plasma View**:
A View rendering a continuously animated, full-screen flowing color field (independent of the poll cadence), which Active Notes perturb: each Active Note adds an outward-travelling ripple centered horizontally by pitch, colored by Track, with amplitude and color/brightness influence from velocity, decaying after note-off. With no Active Notes the field still flows, at a calm, dim baseline. The flow only animates while the Engine's `clock_state` is `running`; paused, stopped, or disconnected freezes it (resuming later continues the flow rather than jumping forward by the paused duration).

**Space View**:
A View rendering a non-interactive vertical-scroller space visualization: each Track gets its own vertical lane, and each of its Active Notes spawns a marker at the top of that lane sized by velocity, which scrolls downward at a tempo-driven pace independent of the note's own duration until it passes the bottom row. A single ship, representing the whole Project, sits at a fixed row near the bottom; its horizontal position follows the pitch of the highest-pitched currently Active Note across all Tracks, resting at center when nothing is sounding. Like Plasma, scrolling only advances while the Engine's `clock_state` is `running`, freezing on pause/stop/disconnect and resuming without jumping ahead.

**Active Note**:
A note currently sounding, derived by cross-referencing a Track's note data with the current Position (i.e. the Position falls within the note's start/duration span). Computed by the Plasma and Space Views; the shared polling layer has no notion of it.
_Avoid_: playing note, live note
