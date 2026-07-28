# Ableton Live → Discord Rich Presence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single Ableton Live Remote Script that shows the current project's name, BPM, and time-since-opened as Discord Rich Presence, with zero manual reconnection step and zero extra running process.

**Architecture:** One Remote Script package (`_Framework.ControlSurface` subclass) running inside Live's own Python process. It talks directly to Discord's local IPC named pipe using a small stdlib-only client. No sockets, no external binary, no `threading` — periodic work uses Live's own `schedule_message` scheduler so all code always runs on Live's main thread.

**Tech Stack:** Python (Live's embedded interpreter, stdlib only — no pip, no third-party packages), Discord IPC (local named pipe, hand-rolled protocol client).

## Global Constraints

- Stdlib only in every file — no `pip install`, no third-party imports. Live's embedded Python has no package manager and some stdlib modules (`_ctypes`, `msvcrt`, `win32api`) are known-missing; do not import them.
- No `threading` / `threading.Timer` anywhere in code that runs inside Live's process. Confirmed by real-world precedent (AbletonOSC's maintainer documents that threading "beachballs" Live) — all periodic work goes through `ControlSurface.schedule_message`, which drains on Live's main thread via `update_display` (~100ms per tick, i.e. `delay_in_ticks=N` ≈ `N * 100ms`, not milliseconds).
- No blocking reads on the Discord pipe. `open()` on a Win32 named pipe returns a plain buffered file object with no read-timeout mechanism available under stdlib-only constraints — a blocking read on Live's main thread risks hanging the whole application. The Discord IPC client is write-only (fire-and-forget): it sends frames and never reads a response. This is a deliberate, documented simplification (see Task 1).
- No exception may propagate out of a `ControlSurface` callback (listener, `schedule_message` callback, `disconnect`) into Live. Every Discord I/O call is wrapped in a narrowly-scoped `try/except OSError`.
- Empty `song.name` (unsaved set) is displayed as `"Undefined"`.
- "Elapsed time" is wall-clock time since the script attached (`time.time()` at `__init__`), not Ableton's `current_song_time` (which is in beats and resets on loop/rewind — unusable as elapsed time, per spec).
- Install location: Ableton Live's User Library `Remote Scripts/` folder, e.g. `%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\Ableton Discord Presence\` on Windows. Live must be restarted after adding a new script folder, and the script must be enabled under Preferences → Link, Tempo & MIDI → Control Surface.

---

### Task 1: Discord IPC client (`discord_ipc.py`)

**Files:**
- Create: `Ableton Discord Presence/discord_ipc.py`

**Interfaces:**
- Produces: `class DiscordIPC` with:
  - `__init__(self, client_id, large_image_key)` — both `str`
  - `connect(self) -> bool` — opens the pipe and sends the handshake; returns whether the pipe open succeeded (does not guarantee Discord accepted the handshake — see write-only note above)
  - `connected` — `bool` attribute, `True` only after a successful `connect()`, flipped to `False` by any I/O failure
  - `set_activity(self, details, state, start_ts) -> None` — `details`/`state` are `str`, `start_ts` is a `float` unix timestamp. No-op if `self.connected` is `False`.
  - `clear_activity(self) -> None` — clears the activity and disconnects. Safe to call when already disconnected.
  - `close(self) -> None` — closes the underlying pipe handle if open. Safe to call multiple times.

This module has **no dependency on `_Framework`/`Live`** — it is plain stdlib Python and runs standalone outside Ableton for manual testing.

- [ ] **Step 1: Write `discord_ipc.py`**

```python
"""Discord Rich Presence IPC client.

Write-only by design: after connect(), every call is a fire-and-forget
write to the local named pipe. We deliberately never read a response.
Reading would block on a plain stdlib file object with no timeout
mechanism, and this code can run on Ableton Live's main thread — a
hung read here would hang Live itself.
ponytail: no error detail from Discord's responses (we don't read them),
upgrade path is overlapped/non-blocking I/O via ctypes if this ever
proves insufficient (not available in Live's embedded Python today).
"""
import json
import os
import struct

OP_HANDSHAKE = 0
OP_FRAME = 1

PIPE_PATH_TEMPLATE = r'\\.\pipe\discord-ipc-%d'
PIPE_SCAN_COUNT = 10


class DiscordIPC(object):

    def __init__(self, client_id, large_image_key):
        self.client_id = client_id
        self.large_image_key = large_image_key
        self.connected = False
        self._pipe = None
        self._nonce = 0

    def connect(self):
        self._close_pipe()
        for i in range(PIPE_SCAN_COUNT):
            path = PIPE_PATH_TEMPLATE % i
            try:
                self._pipe = open(path, 'r+b', buffering=0)
            except OSError:
                continue
            break
        else:
            self.connected = False
            return False

        handshake = json.dumps({'v': 1, 'client_id': self.client_id}).encode('utf-8')
        try:
            self._write_frame(OP_HANDSHAKE, handshake)
        except OSError:
            self._close_pipe()
            self.connected = False
            return False

        self.connected = True
        return True

    def set_activity(self, details, state, start_ts):
        if not self.connected:
            return
        payload = {
            'cmd': 'SET_ACTIVITY',
            'args': {
                'pid': os.getpid(),
                'activity': {
                    'details': details,
                    'state': state,
                    'assets': {
                        'large_image': self.large_image_key,
                        'large_text': details,
                    },
                    'timestamps': {'start': int(start_ts)},
                },
            },
            'nonce': self._next_nonce(),
        }
        self._send(payload)

    def clear_activity(self):
        if self.connected:
            payload = {
                'cmd': 'SET_ACTIVITY',
                'args': {'pid': os.getpid(), 'activity': None},
                'nonce': self._next_nonce(),
            }
            self._send(payload)
        self.connected = False
        self._close_pipe()

    def close(self):
        self._close_pipe()

    def _send(self, payload):
        try:
            self._write_frame(OP_FRAME, json.dumps(payload).encode('utf-8'))
        except OSError:
            self.connected = False
            self._close_pipe()

    def _write_frame(self, opcode, payload_bytes):
        header = struct.pack('<II', opcode, len(payload_bytes))
        self._pipe.write(header + payload_bytes)

    def _next_nonce(self):
        self._nonce += 1
        return str(self._nonce)

    def _close_pipe(self):
        if self._pipe is not None:
            try:
                self._pipe.close()
            except OSError:
                pass
            self._pipe = None


if __name__ == '__main__':
    import sys
    import time

    client_id = sys.argv[1] if len(sys.argv) > 1 else input('Discord Client ID: ')
    image_key = sys.argv[2] if len(sys.argv) > 2 else 'ableton_logo'

    ipc = DiscordIPC(client_id, image_key)
    ok = ipc.connect()
    print('connect() ->', ok)
    assert ok, 'Could not open a Discord IPC pipe — is Discord running?'

    ipc.set_activity(details='Smoke Test Project', state='120 BPM', start_ts=time.time())
    print('SET_ACTIVITY sent — check your Discord profile now.')
    time.sleep(15)

    ipc.clear_activity()
    ipc.close()
    print('Activity cleared, pipe closed. Smoke test done.')
```

- [ ] **Step 2: Run the standalone smoke test**

Run (outside Ableton, with Discord desktop client running and logged in, from a regular desktop Python 3 install):

```bash
cd "Ableton Discord Presence"
python discord_ipc.py YOUR_DISCORD_CLIENT_ID ableton_logo
```

Expected: prints `connect() -> True`, then `SET_ACTIVITY sent...`. Within a few seconds your own Discord profile (client → your username → user card, or Settings → Activity Status preview) shows "Smoke Test Project" / "120 BPM" with an elapsed timer counting up. After 15s it clears and prints `Activity cleared, pipe closed. Smoke test done.`

If `connect()` prints `False`: confirm Discord desktop is running and you are logged in (not just the browser). This is the expected, non-error state the real script must also tolerate gracefully — see Task 2.

You will need a `YOUR_DISCORD_CLIENT_ID` from a Discord Application — see Task 3 for how to create one; you can run this step later, after Task 3's setup, before doing the final end-to-end check. It's fine to skip actually running Step 2 right now and come back to it once you have a Client ID — the code review / correctness check for this task does not require it, but do run it before Task 4's final verification.

- [ ] **Step 3: Commit**

```bash
git add "Ableton Discord Presence/discord_ipc.py"
git commit -m "Add stdlib-only Discord IPC client"
```

---

### Task 2: Live-side Remote Script (`presence.py`, `__init__.py`)

**Files:**
- Create: `Ableton Discord Presence/presence.py`
- Create: `Ableton Discord Presence/__init__.py`

**Interfaces:**
- Consumes: `discord_ipc.DiscordIPC` — `__init__(client_id, large_image_key)`, `.connected` (bool), `.connect()`, `.set_activity(details, state, start_ts)`, `.clear_activity()`, `.close()` (all from Task 1).
- Produces: `class PresenceControlSurface(ControlSurface)` in `presence.py`; `create_instance(c_instance)` in `__init__.py` (the entry point Live's control-surface loader calls directly).

- [ ] **Step 1: Write `presence.py`**

```python
"""Ableton Live Remote Script: pushes project name/BPM/elapsed time to
Discord Rich Presence. Runs entirely on Live's main thread — no
threading module usage (see docs/superpowers/plans for why)."""
import time

from _Framework.ControlSurface import ControlSurface

from .discord_ipc import DiscordIPC

# Fill these in after creating a Discord Application — see README.md.
DISCORD_CLIENT_ID = 'REPLACE_WITH_YOUR_DISCORD_CLIENT_ID'
LARGE_IMAGE_KEY = 'ableton_logo'

UNDEFINED_NAME = 'Undefined'
TICK_INTERVAL_TICKS = 50  # ~5s; schedule_message ticks are ~100ms each


class PresenceControlSurface(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._ipc = DiscordIPC(DISCORD_CLIENT_ID, LARGE_IMAGE_KEY)
        self._start_ts = time.time()
        self._ipc.connect()
        self._push_activity()

        song = self.song()
        song.add_tempo_listener(self._on_tempo_changed)

        self.schedule_message(TICK_INTERVAL_TICKS, self._on_tick)

    def _on_tempo_changed(self):
        self._push_activity()

    def _on_tick(self):
        if not self._ipc.connected:
            self._ipc.connect()
        self._push_activity()
        self.schedule_message(TICK_INTERVAL_TICKS, self._on_tick)

    def _push_activity(self):
        song = self.song()
        name = song.name if song.name else UNDEFINED_NAME
        bpm = int(song.tempo)
        self._ipc.set_activity(
            details=name,
            state='%d BPM' % bpm,
            start_ts=self._start_ts,
        )

    def disconnect(self):
        song = self.song()
        song.remove_tempo_listener(self._on_tempo_changed)
        self._ipc.clear_activity()
        self._ipc.close()
        ControlSurface.disconnect(self)
```

- [ ] **Step 2: Write `__init__.py`**

```python
from .presence import PresenceControlSurface


def create_instance(c_instance):
    return PresenceControlSurface(c_instance)
```

- [ ] **Step 3: Verify by static read-through (no automated test runner available inside Live's sandbox)**

Re-read both files against this checklist — this substitutes for a unit test since `_Framework.ControlSurface` cannot be imported or instantiated outside Live:
- [ ] Every call into `song` (`song.name`, `song.tempo`, `add_tempo_listener`, `remove_tempo_listener`) matches the names verified in the design spec's research summary.
- [ ] `schedule_message` is called with `delay_in_ticks >= 1` everywhere (never `0`) — `TICK_INTERVAL_TICKS = 50` satisfies this.
- [ ] No `import threading` anywhere in either file.
- [ ] `disconnect()` removes the listener it added in `__init__` and calls `ControlSurface.disconnect(self)` last.
- [ ] Full end-to-end behavior is verified in Task 4, inside real Ableton Live — that is the actual test for this task.

- [ ] **Step 4: Commit**

```bash
git add "Ableton Discord Presence/presence.py" "Ableton Discord Presence/__init__.py"
git commit -m "Add Live Remote Script control surface"
```

---

### Task 3: Discord Application setup + install instructions (`README.md`)

**Files:**
- Create: `README.md` (project root)

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: the `DISCORD_CLIENT_ID` and `LARGE_IMAGE_KEY` values that Task 2's `presence.py` needs filled in, and the installed script folder that Task 4 verifies end-to-end.

- [ ] **Step 1: Create the Discord Application (manual, one-time)**

Document these steps in `README.md` under a "Setup" heading — the user performs them once:
1. Go to the Discord Developer Portal (discord.com/developers/applications), click "New Application", name it (e.g. "Ableton Live").
2. Copy the "Application ID" shown on the General Information page — this is `DISCORD_CLIENT_ID`.
3. Go to "Rich Presence" → "Art Assets" in the left sidebar. Upload a square PNG (≥512×512) of the Ableton Live logo. Give it the asset key `ableton_logo` (lowercase, matches `LARGE_IMAGE_KEY` in `presence.py`). Save changes. (Propagation can take a few minutes before the image shows up live.)

- [ ] **Step 2: Write `README.md`**

```markdown
# Ableton Live → Discord Rich Presence

Shows your Ableton Live project (name, BPM, time since opened) as Discord
Rich Presence. Runs entirely inside Ableton — no separate app to keep running.

## Setup (one-time)

1. Create a Discord Application at https://discord.com/developers/applications
   → "New Application" → name it anything (e.g. "Ableton Live").
2. Copy the **Application ID** from the General Information page.
3. In the same application, go to **Rich Presence → Art Assets**, upload a
   square PNG (512×512+) of the Ableton Live logo, and set its asset key to
   `ableton_logo`. Save. (Can take a few minutes to propagate.)
4. Open `Ableton Discord Presence/presence.py` in this folder and replace
   `DISCORD_CLIENT_ID = 'REPLACE_WITH_YOUR_DISCORD_CLIENT_ID'` with the
   Application ID from step 2.

## Install

1. Copy the entire `Ableton Discord Presence` folder into Ableton Live's
   User Library Remote Scripts directory:
   `%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\`
   (create the `Remote Scripts` folder if it doesn't exist yet).
2. Restart Ableton Live.
3. Open Preferences → Link, Tempo & MIDI → in the Control Surface dropdown
   (any empty slot), select "Ableton Discord Presence".
4. Open or save a project. Your Discord profile should show the project
   name, BPM, and an elapsed-time counter within a few seconds.

## Notes

- An unsaved project shows as "Undefined" until you save it once (Ableton
  only assigns a name on save).
- If Discord isn't running yet when Live starts, the script keeps retrying
  in the background — no manual reconnect needed.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Add setup and install instructions"
```

---

### Task 4: End-to-end verification in real Ableton Live

**Files:**
- None created or modified — this task is manual verification only, using the files from Tasks 1–3.

**Interfaces:**
- Consumes: the installed `Ableton Discord Presence/` folder (Tasks 1–2) and the `DISCORD_CLIENT_ID`/asset key from Task 3.
- Produces: confirmation the whole system works together, per the spec's testing section.

- [ ] **Step 1: Run the Task 1 smoke test with your real Client ID (if not already done)**

```bash
cd "Ableton Discord Presence"
python discord_ipc.py YOUR_DISCORD_CLIENT_ID ableton_logo
```
Confirm your Discord profile briefly shows "Smoke Test Project" / "120 BPM" with the Ableton logo image and elapsed timer, then clears after 15s.

- [ ] **Step 2: Install into Live and enable the control surface**

Follow the README's "Install" section exactly (copy folder to User Library `Remote Scripts/`, restart Live, enable in Preferences → Link, Tempo & MIDI).

- [ ] **Step 3: Verify with an unsaved set**

Open a new, never-saved Live set. Confirm Discord shows `Undefined` as the details line and the correct BPM.

- [ ] **Step 4: Verify with a saved set**

Save the set with a real name (e.g. "My Track"). Confirm Discord updates within ~5s (next tick) to show that name.

- [ ] **Step 5: Verify tempo changes propagate**

Change the project tempo in Live. Confirm Discord's BPM updates promptly (via the tempo listener, not waiting for the next 5s tick).

- [ ] **Step 6: Verify elapsed time behaves as wall-clock-since-open**

Confirm Discord's elapsed counter keeps counting up continuously, including while playback is stopped, and does not reset when you rewind or loop playback in Live.

- [ ] **Step 7: Verify graceful handling of Discord being closed**

With Live still running and the set open, quit Discord entirely. Confirm Live does not crash, freeze, or show any error (check Live's status bar / log for absence of tracebacks from this script). Relaunch Discord. Within ~5s (next tick), confirm Rich Presence reappears with the current project's correct data.

- [ ] **Step 8: Verify clean disconnect**

Close the Live set (or quit Live). Confirm the Rich Presence activity disappears from your Discord profile rather than staying stuck on stale data.

- [ ] **Step 9: Commit any README fixes found during verification**

If any step above required correcting the install instructions, amend `README.md` and commit:

```bash
git add README.md
git commit -m "Fix install instructions found during end-to-end verification"
```
