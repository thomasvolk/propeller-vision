# 05 — Plasma view: flowing field (supersedes 04)

**What to build:** Replace the per-pitch flash row from ticket 04 with a continuously animated, full-screen flowing plasma field (à la `ascii_plasma.py`), which Active Notes perturb rather than solely drive. Rendering runs on its own frame timer, decoupled from the Engine poll cadence, so the flow reads as smooth motion.

**Blocked by:** 04

**Status:** ready-for-agent

- [x] `PlasmaView` fills the full terminal area (not a single row) with background-color-filled cells, truecolor
- [x] Rendering runs on an independent per-frame timer (~20fps), separate from the poll-driven update of which notes are active
- [x] With no Active Notes, the field still flows continuously at a calm, dim baseline (idle HSV lower than fully energized)
- [x] Each Active Note adds a ripple to the field: an outward-travelling wave centered at a point derived from the note's pitch (horizontal position; fixed mid-row), added into the base flow so it visibly distorts the field's shape
- [x] Each Active Note's ripple locally raises saturation/value toward full intensity and blends in its Track's hue (golden-angle scheme, same as ticket 04), both scaled by one velocity-derived intensity scalar; influence fades spatially with distance from the ripple's source and follows the same sustain-while-active + ~100ms decay-after-note-off lifecycle as ticket 04's `Glow`
- [x] Multiple simultaneous notes each contribute independently (their wave terms sum into the field; the strongest nearby influence wins for color/brightness blending at a given cell)
- [x] Disconnected state unchanged: shows the shared "Waiting for engine..." message instead of animating
- [x] The flow freezes (stops animating, holds the last rendered frame) whenever the Engine's `status.clock_state` is anything other than `running` (paused, stopped, or absent) -- not just when disconnected; resuming afterward continues the flow rather than jumping forward by the paused duration
- [x] No numpy or other new dependency; pure Python per-cell computation, matching `ascii_plasma.py`'s approach
- [x] Test: pure functions for the field/ripple math (base field value, ripple wave/weight, hue blending, idle vs. energized HSV) are unit-tested with fixed time/coordinate inputs; app-level test confirms the view renders a full grid sized to the widget once connected, and the waiting message while disconnected

**Known limitation:** per-cell Python computation is comfortable at common terminal sizes (~120×35 renders in ~18ms/frame) but gets tight on very large terminals (~200+ columns measured at ~64ms/frame, over the 50ms budget for 20fps). Not addressed here; revisit if it proves disruptive in practice.
