# Currently-active notes are in scope; full note detail rendering is not

The Plasma view needs to react to played notes in real time, which requires deriving "which notes are currently sounding" from the `project` track/note data cross-referenced with the current `Position`. This refines ADR-0002: computing and consuming *active notes* (a narrow, derived signal) is in scope, but a piano-roll/track-editor style view rendering full note detail remains out of scope. Dashboard doesn't use this data at all; only Plasma does.
