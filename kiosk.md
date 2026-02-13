# Poetry Kiosk for Pimoroni Presto — Spec

## Overview
A MicroPython kiosk app for the Pimoroni Presto that displays a looping “slide” consisting of a photo with a poem overlaid. The app shuffles the poem order once on boot (deterministic seed during development), fades in from black into the first slide, displays it for a fixed duration, then fades out to black and advances.

A future enhancement will add a proximity sensor to pause/blank the display when no one is nearby to reduce burn-in risk.

## Platform and Constraints
- Device: Pimoroni Presto
- Display: 480×480 full resolution (`Presto(full_res=True)`)
- Storage: on-device flash (QSPI), photos and poems stored under `/data`
- Memory: 8MB PSRAM available; prefer single framebuffer and backlight fades
- Python runtime: MicroPython
- Logging: `print()`

## Content Model and Storage Layout

### Identifiers
- A poem’s **id** is the basename of its poem JSON filename:
  - `/data/poems/<id>.json` → `id = <id>`

### Filesystem Layout
- Poems: `/data/poems/<id>.json`
- Photos: `/data/photos/<id>.jpg`

### Inclusion Rules
- On boot, build the playlist by scanning `/data/poems` for `*.json`.
- For each poem `<id>.json`, include regardless if the corresponding photo exists:
  - `/data/photos/<id>.jpg`
- If a photo exists without a matching poem JSON, it is ignored (photos are not discovered independently).

### Poem JSON Schema
Each poem JSON must contain:
- `title`: string
- `body`: string (UTF-8)

Rules:
- Explicit newlines in `body` are respected (blank lines preserved).
- If JSON is invalid or missing required keys/types, skip and log.

## Playlist and Ordering
- Build playlist as a list of poem ids.
- Deterministic base ordering:
  - sort ids, then shuffle once at boot
- Seed:
  - fixed seed during development (debug); may switch to non-deterministic later
- Looping:
  - when playlist ends, repeat in the same order (no reshuffle)

### Optional fixed first poem
- App may be configured with `start_poem_id`.
- If present and exists in playlist:
  - remove it from its shuffled position and insert it at index 0
- Remaining poems retain shuffled order.

## Display and Rendering

### Photos
- JPEG files, preprocessed offline to **480×480** and cropped.
- JPEG decode occurs directly into the display framebuffer (no full decoded image buffer retained in Python).

### Text Rendering
- Font: `bitmap8`
- Colors:
  - poem text: white
  - shadow: black, 1px offset
- No metadata (only title + body).

### Layout
- Margins:
  - 10px on all sides (symmetric)
- Line spacing:
  - 2px between lines (configurable in code)
- Title:
  - rendered at 2× scale relative to body (configurable)
  - remains visible on every page
  - title height is included in page height calculations

### Background dimming
- Background is dimmed slightly to improve readability.
- Dim applies to the **whole photo**, not just a text box.
- Implementation may use:
  - alpha overlay if supported, otherwise
  - a lightweight dither pattern (acceptable approximation)

## Pagination
- Wrap rule:
  - word wrap using `display.measure_text` (existing `wrap_words` function)
  - falls back to character wrapping for words wider than the usable width
- Page break rule:
  - pages determined by **rendered pixel height**
  - title consumes vertical space on every page

## Interaction and Timing

### Timings
- Dwell time:
  - 30 seconds per poem (global default)
- Fade durations:
  - 2 second fade-in, 2 second fade-out
- Easing:
  - smoothstep (“ease in/out”)

### Start-up behavior
- App must start with a fade-in **from black**:
  - set backlight to 0
  - render first slide while backlight is 0
  - fade backlight up to target

### Touch
- Touch is ignored during fades.
- During display:
  - touch advances to next page
  - on last page, wraps back to first page
  - any touch resets the timer and prevents an imminent fade

## Transitions
- Transition mechanism: backlight fade (uniform fade is acceptable).
- Brightness scale:
  - config expressed as 0–100%
  - device API requires 0.0–1.0 float; conversion performed at the boundary.

### Extensibility
- Transitions are implemented behind a swappable interface (e.g., `Transition.start()` / `Transition.update()`), so alternative fade algorithms can be substituted later without rewriting the app state machine.

## App State Machine
Core states:
- `LOAD`: load current poem, paginate, render current page (while backlight is 0 for first item)
- `FADE_IN`: backlight fade from 0 → target
- `DISPLAY`: wait until deadline; accept touch paging; reset deadline on touch
- `FADE_OUT`: backlight fade from target → 0; then advance to next poem and return to `LOAD`

## Error Handling
- Missing photo for a poem id: show poem on black background
- Invalid JSON or missing keys/types: skip poem and log
- If no valid poem/photo pairs exist:
  - show black screen with a message (and remain idle)

## Future Enhancements (Not Implemented Yet)
- Proximity sensor:
  - if no presence detected for a period, blank/dim display to reduce burn-in
  - define sensor-driven states (e.g., `ACTIVE`, `IDLE`, `WAKING`) without requiring architectural changes
- Night mode:
  - cap `backlight_max` or adjust dim strength

## Implementation Notes
- Prefer single framebuffer and avoid layers unless needed.
- Avoid per-frame allocations in the hot path to reduce fragmentation.
- Keep renderer pure (no input handling); touch/presence belongs to app/controller layer.
