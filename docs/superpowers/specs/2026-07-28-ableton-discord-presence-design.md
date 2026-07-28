# Ableton Live → Discord Rich Presence — Design

## Problem

Show what's happening in Ableton Live (project name, BPM, elapsed time) as Discord Rich Presence, with zero manual connection step and near-zero RAM/CPU footprint.

## Research summary

- Live's embedded Python (3.x, version varies by Live version) has no pip / third-party packages — stdlib only, and even some stdlib modules (`_ctypes`, `msvcrt`, `win32api`) are stripped. `socket`, `threading`, `json` are confirmed working.
- `socket`+`threading` are reliably usable inside Live's process (proven by AbletonMCP, AbletonOSC, and existing Ableton→Discord projects), as long as `Live.*`/LOM objects are only touched from Live's main thread.
- `song.name` is empty until the set is saved at least once. `song.tempo` (float BPM) and `song.is_playing` (bool) both support the `add_<prop>_listener` / `remove_<prop>_listener` pattern. `song.current_song_time` is in **beats**, resets on loop/rewind — not usable as wall-clock elapsed time.
- Discord Rich Presence is driven over a local named pipe (`\\.\pipe\discord-ipc-N`) with a length-prefixed JSON frame protocol. On Windows this pipe is a normal file handle — `open()` + `struct` + `json` (all stdlib) are sufficient to speak it; no `pywin32`/`ctypes` required. Requires a Discord Application (Client ID) from the Developer Portal, and image assets must be pre-uploaded as "Art Assets" on that application.
- Existing prior art (`mlntcandy/AbletonDiscordPresence`) proves the "no external process, talk to Discord directly from inside Live's Python" architecture works in practice.
- A Windows Service is the wrong shape for this (Session 0 isolation blocks access to the user's Discord pipe) — moot here since we're not running a separate service at all.

## Approach: single in-process Remote Script

Everything runs **inside Ableton Live's process** as one Remote Script. No external service, no separate executable, no sockets between processes. The script talks directly to Discord's local IPC pipe using stdlib only.

**Why this over an external-process + local-socket bridge:** the external-process approach (a separate Go/Python binary polling a socket the Live script opens) adds a whole extra running process, its own RAM/CPU baseline, its own autostart mechanism (Scheduled Task/Startup folder), and its own retry logic against two independent connections (to Live, to Discord) instead of one. Since Discord's IPC pipe is directly reachable with pure stdlib from inside Live's Python, the bridge buys robustness (presence survives a Live crash) at the cost of literally doubling the moving parts — for a personal tool, not worth it. This is also proven prior art (`mlntcandy/AbletonDiscordPresence`), not a novel risk.

**Trade-off accepted:** if Live crashes, the Discord presence disappears with it (no separate watchdog process to clear/hold state). This is acceptable — a crashed Live meaning "no more presence" is arguably correct behavior anyway.

## Components

Single Remote Script folder, installed under Live's User Library `Remote Scripts/` directory:

```
Ableton Discord Presence/
  __init__.py       # Live entry point: create_instance(c_instance)
  presence.py        # ControlSurface subclass: Live-side logic, listeners, timer
  discord_ipc.py      # Discord RPC pipe client: handshake, framing, reconnect
```

- **`__init__.py`** — the only file Live's control-surface loader calls directly. Just wires `create_instance` to the `PresenceControlSurface` class.
- **`presence.py`** — a `_Framework.ControlSurface` subclass. On init: opens a `DiscordIPC` client, registers `add_tempo_listener` on `song`, and schedules a recurring ~5s tick (via Live's own scheduling, not a Python thread) for: retrying the Discord connection when disconnected, and refreshing `song.name` in case the set was saved/renamed since last check. Builds the activity payload and calls `discord_ipc.set_activity(...)`. On `disconnect()` (Live closes the set / switches control surfaces), clears the Discord activity and removes listeners.

  `is_playing` is deliberately not listened to: the chosen "elapsed time" is wall-clock since the script attached (not playback-dependent), and play/pause state is out of scope for the minimal field set — see "Explicitly out of scope" below. Adding the listener now with no consumer would be dead weight.
- **`discord_ipc.py`** — minimal Discord RPC client, stdlib only (`struct`, `json`, `os`, `time`). Handles: handshake (opcode 0), `SET_ACTIVITY` frames (opcode 1), and reconnection with backoff when the pipe is missing or breaks. Exposes a small interface: `connect()`, `set_activity(details, state, start_ts)`, `clear_activity()`, `close()`. Framed as a standalone module runnable outside Live for manual smoke testing (`if __name__ == "__main__":`).

## Data flow

1. Live loads the script when a set is opened → `create_instance` → `PresenceControlSurface.__init__`.
2. `__init__` attempts the Discord handshake; registers tempo/is_playing listeners; schedules the periodic tick; records `start_ts = time.time()` once (this is the "elapsed time" origin — wall-clock from when the script attached, not playback position).
3. Each listener callback (tempo changed) or periodic tick rebuilds the full activity payload and re-sends it — Discord's protocol requires the whole activity object on every update, not a diff:
   - `details` = `song.name` if non-empty, else `"Undefined"`
   - `state` = `f"{int(song.tempo)} BPM"` (+ optionally a play/pause glyph — deferred, see below)
   - `assets.large_image` = pre-uploaded Ableton logo asset key, `large_text` = same as `details`
   - `timestamps.start` = the `start_ts` recorded once at attach (Discord renders this as a live-ticking elapsed counter — no manual formatting needed)
4. `discord_ipc.set_activity(...)` writes the framed JSON to the pipe. Any I/O error marks the client disconnected; the next periodic tick retries the handshake. No exception is allowed to propagate back into Live.
5. On `disconnect()`: send an empty/cleared activity, remove listeners, close the pipe handle.

## Error handling

- **Discord not running / pipe absent** — `open()` raises `FileNotFoundError`; caught, client marked disconnected, retried on next tick. This is the expected common case for a background presence tool, not an error condition to surface.
- **Pipe breaks mid-session** (Discord closed while connected) — `OSError`/`BrokenPipeError` caught the same way, same reconnect path.
- **Unsaved set** — empty `song.name` is replaced with `"Undefined"` per the original requirement.
- All Discord I/O is wrapped in narrowly-scoped try/except inside `discord_ipc.py`; a failure there must never raise into Live's control-surface callbacks, since that risks disrupting the audio/UI thread.

## Explicitly out of scope (deferred)

- **Installer/wizard** for non-technical users (auto-locate the Remote Scripts folder, copy files, prompt for Discord Client ID) — user confirmed this is wanted later, not now. Today's scope is a manually-installed script for personal use.
- Extra Rich Presence fields (track count, play/pause glyph, party size, buttons) — user chose the minimal set (name, BPM, elapsed time) to start.
- "Time spent actively playing" (pause-aware accumulator) — user chose simple wall-clock-since-open instead.

## Testing

No test runner is practical inside Live's sandboxed process. Two-tier verification instead:
1. **Standalone smoke test** — `discord_ipc.py` runs standalone outside Live (`python discord_ipc.py`) against a real local Discord client, doing a real handshake + `SET_ACTIVITY`, to validate the framing/protocol logic in isolation before ever touching Ableton.
2. **End-to-end manual verification** — install the script, open Ableton Live with a saved and an unsaved set, confirm the Discord profile shows the correct name/BPM/elapsed time, confirm behavior when Discord is closed/reopened while Live keeps running, confirm `"Undefined"` shows for an unsaved set.

## Prerequisites (user-provided, one-time)

- A Discord Application created in the Developer Portal → its Client ID (hardcoded into `discord_ipc.py` or a small config constant).
- The Ableton Live logo image uploaded as an Art Asset on that application, with a known asset key.
