# QoL Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Label the Discord Rich Presence fields, show the project's scale on Live 12+, and ship a double-click `.exe` setup wizard so anyone can install without editing Python.

**Architecture:** Two small pure-logic modules (`activity_text.py`, `installer/wizard_logic.py`) hold everything that can be reasoned about and self-checked outside Ableton/tkinter; `presence.py` and `installer/setup_wizard.py` stay thin wiring layers around them, matching the existing split where `discord_ipc.py` is the testable core and `presence.py` is the Live-only wiring.

**Tech Stack:** Python (stdlib only) for the Remote Script, unchanged. `tkinter` (stdlib) + `PyInstaller` (new dev-only, build-time dependency) for the installer wizard.

## Global Constraints

- Windows-only project — no cross-platform fallback code anywhere (matches existing `discord_ipc.py` scope).
- Stdlib only at runtime; `PyInstaller` is a **build-time-only** dependency for the maintainer, never required by end users or by the Remote Script itself.
- Keep the codebase's existing `%`-style string formatting (no f-strings) — `discord_ipc.py` and `presence.py` both use it today.
- Discord Client ID (shared, hardcoded, public — not a secret): `1531793691486716096`.
- GitHub repo: `https://github.com/DA0806/Ableton-Discord-Presence`, default branch `master`.
- Note names use sharps: `['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']`, indexed by `root_note` (0=C).
- Scale is only shown in Discord when `song.scale_mode is True`; `hasattr(song, 'scale_mode')` gates all Live-<12 fallback.

---

### Task 1: `activity_text.py` — pure Rich Presence text formatter

**Files:**
- Create: `AbletonDiscordPresence/activity_text.py`

**Interfaces:**
- Produces: `format_activity(name, bpm, scale_mode=False, root_note=None, scale_name=None) -> (details: str, state: str)` — used by Task 2.
- Produces: `NOTE_NAMES` (list of 12 str) and `UNDEFINED_NAME = 'Undefined'` — used by Task 2.

- [ ] **Step 1: Write the file with a stub that fails**

```python
"""Pure Discord Rich Presence text formatting for AbletonDiscordPresence.
No Live/_Framework dependency — importable and testable outside Ableton,
unlike presence.py which requires _Framework.ControlSurface."""

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
UNDEFINED_NAME = 'Undefined'


def format_activity(name, bpm, scale_mode=False, root_note=None, scale_name=None):
    raise NotImplementedError


if __name__ == '__main__':
    assert format_activity('My Set', 120) == ('Project: My Set', 'BPM: 120')
    assert format_activity('', 120) == ('Project: Undefined', 'BPM: 120')
    assert format_activity(
        'My Set', 120, scale_mode=False, root_note=0, scale_name='Major'
    ) == ('Project: My Set', 'BPM: 120')
    assert format_activity(
        'My Set', 120, scale_mode=True, root_note=0, scale_name='Major'
    ) == ('Project: My Set', 'BPM: 120 · C Major')
    assert format_activity(
        'My Set', 98, scale_mode=True, root_note=9, scale_name='Minor'
    ) == ('Project: My Set', 'BPM: 98 · A Minor')
    print('activity_text: all checks passed')
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `python AbletonDiscordPresence/activity_text.py`
Expected: `NotImplementedError` raised from the first `format_activity(...)` call.

- [ ] **Step 3: Implement `format_activity`**

Replace the `raise NotImplementedError` body with:

```python
def format_activity(name, bpm, scale_mode=False, root_note=None, scale_name=None):
    """Build the (details, state) pair for Discord's SET_ACTIVITY payload.

    Leave scale_mode/root_note/scale_name at their defaults on Live
    versions where Song has no scale_mode attribute (pre-Live 12)."""
    details = 'Project: %s' % (name if name else UNDEFINED_NAME)
    if scale_mode and root_note is not None and scale_name:
        state = 'BPM: %d · %s %s' % (bpm, NOTE_NAMES[root_note], scale_name)
    else:
        state = 'BPM: %d' % bpm
    return details, state
```

- [ ] **Step 4: Run it again, confirm it passes**

Run: `python AbletonDiscordPresence/activity_text.py`
Expected: prints `activity_text: all checks passed`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add AbletonDiscordPresence/activity_text.py
git commit -m "Add pure Rich Presence text formatter with scale support"
```

---

### Task 2: Wire scale display + labels into `presence.py`

**Files:**
- Modify: `AbletonDiscordPresence/presence.py` (whole file — see below)

**Interfaces:**
- Consumes: `format_activity`, `NOTE_NAMES`, `UNDEFINED_NAME` from Task 1's `AbletonDiscordPresence/activity_text.py`.
- Consumes: `DiscordIPC.set_activity(details, state, start_ts)` (unchanged, from existing `discord_ipc.py`).

- [ ] **Step 1: Replace the full file contents**

```python
"""Ableton Live Remote Script: pushes project name/BPM/scale to Discord
Rich Presence. Runs entirely on Live's main thread — no threading module
usage (see docs/superpowers/plans for why)."""
import time

from _Framework.ControlSurface import ControlSurface

from .activity_text import format_activity
from .discord_ipc import DiscordIPC

# Shared Discord Application owned by the project maintainer — every
# install uses this same Client ID. Discord's IPC handshake never uses a
# client secret, so a Client ID is a public identifier, safe to commit.
DISCORD_CLIENT_ID = '1531793691486716096'
LARGE_IMAGE_KEY = 'ableton_logo'

TICK_INTERVAL_TICKS = 50  # ~5s; schedule_message ticks are ~100ms each


class PresenceControlSurface(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._disconnected = False
        self._ipc = DiscordIPC(DISCORD_CLIENT_ID, LARGE_IMAGE_KEY)
        self._start_ts = time.time()
        ok = self._ipc.connect()
        self.log_message('AbletonDiscordPresence: connect() -> %s' % ok)
        self._push_activity()

        song = self.song()
        song.add_tempo_listener(self._on_tempo_changed)
        self._has_scale_api = hasattr(song, 'scale_mode')
        if self._has_scale_api:
            song.add_scale_mode_listener(self._on_scale_changed)
            song.add_root_note_listener(self._on_scale_changed)
            song.add_scale_name_listener(self._on_scale_changed)

        self.schedule_message(TICK_INTERVAL_TICKS, self._on_tick)

    def _on_tempo_changed(self):
        self._push_activity()

    def _on_scale_changed(self):
        self._push_activity()

    def _on_tick(self):
        if self._disconnected:
            return
        if not self._ipc.connected:
            self._ipc.connect()
        self._push_activity()
        self.schedule_message(TICK_INTERVAL_TICKS, self._on_tick)

    def _push_activity(self):
        if self._disconnected:
            return
        try:
            song = self.song()
            bpm = int(song.tempo)
            if self._has_scale_api:
                details, state = format_activity(
                    song.name, bpm,
                    scale_mode=song.scale_mode,
                    root_note=song.root_note,
                    scale_name=song.scale_name,
                )
            else:
                details, state = format_activity(song.name, bpm)
            self._ipc.set_activity(
                details=details,
                state=state,
                start_ts=self._start_ts,
            )
        except Exception:
            pass

    def disconnect(self):
        self._disconnected = True
        self._ipc.clear_activity()
        self._ipc.close()
        try:
            song = self.song()
            song.remove_tempo_listener(self._on_tempo_changed)
            if self._has_scale_api:
                song.remove_scale_mode_listener(self._on_scale_changed)
                song.remove_root_note_listener(self._on_scale_changed)
                song.remove_scale_name_listener(self._on_scale_changed)
        except RuntimeError:
            pass
        ControlSurface.disconnect(self)
```

- [ ] **Step 2: Manual verification (no automated runner exists inside Live — see original design doc)**

1. Copy the updated `AbletonDiscordPresence/` folder to the Remote Scripts folder (manually, for now — Task 4 automates this).
2. Restart Live, open a saved Live 12 set. Confirm Discord shows `Project: <name>` / `BPM: <n>`.
3. Turn on Scale Awareness for that set (bottom bar scale selector) and pick a key/scale. Confirm the Discord state line becomes `BPM: <n> · <Note> <Scale>` within ~5s, and updates live when you change the key or scale.
4. Turn Scale Awareness back off. Confirm the state line reverts to `BPM: <n>` only.
5. If you have access to a Live <12 install, confirm it behaves exactly as before (no scale text, no errors in `Log.txt`).

- [ ] **Step 3: Commit**

```bash
git add AbletonDiscordPresence/presence.py
git commit -m "Add Project:/BPM: labels and Live 12 scale display"
```

---

### Task 3: `installer/wizard_logic.py` — pure install logic

**Files:**
- Create: `installer/wizard_logic.py`

**Interfaces:**
- Produces: `get_remote_scripts_path() -> str` — used by Task 4.
- Produces: `is_existing_install(remote_scripts_path: str) -> bool` — used by Task 4.
- Produces: `install(source_dir: str, remote_scripts_path: str) -> str` (returns the final destination path, raises `OSError` on failure) — used by Task 4.
- Produces: `SCRIPT_FOLDER_NAME = 'AbletonDiscordPresence'` — used by Task 4.

- [ ] **Step 1: Write the file with stubs that fail**

```python
"""Pure installer logic for the AbletonDiscordPresence setup wizard — no
tkinter/GUI dependency, so it's testable as a plain script. The GUI
(setup_wizard.py) only calls these functions and renders their results."""
import ctypes
import os
import shutil
import uuid

FOLDERID_DOCUMENTS = 'FDD39AD0-238F-46AF-ADB4-6C85480369C7'
REMOTE_SCRIPTS_SUBPATH = ('Ableton', 'User Library', 'Remote Scripts')
SCRIPT_FOLDER_NAME = 'AbletonDiscordPresence'


class _GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', ctypes.c_uint32),
        ('Data2', ctypes.c_uint16),
        ('Data3', ctypes.c_uint16),
        ('Data4', ctypes.c_uint8 * 8),
    ]


def get_default_documents_path():
    raise NotImplementedError


def get_remote_scripts_path():
    return os.path.join(get_default_documents_path(), *REMOTE_SCRIPTS_SUBPATH)


def is_existing_install(remote_scripts_path):
    return os.path.isdir(os.path.join(remote_scripts_path, SCRIPT_FOLDER_NAME))


def install(source_dir, remote_scripts_path):
    raise NotImplementedError


if __name__ == '__main__':
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        source = os.path.join(tmp, 'AbletonDiscordPresence')
        os.makedirs(source)
        with open(os.path.join(source, '__init__.py'), 'w') as f:
            f.write('# stub')

        remote_scripts = os.path.join(tmp, 'Remote Scripts')
        assert not is_existing_install(remote_scripts)

        dest = install(source, remote_scripts)
        assert os.path.isfile(os.path.join(dest, '__init__.py'))
        assert is_existing_install(remote_scripts)

        # Re-install must overwrite cleanly (update path), not error.
        with open(os.path.join(source, '__init__.py'), 'w') as f:
            f.write('# updated stub')
        dest2 = install(source, remote_scripts)
        with open(os.path.join(dest2, '__init__.py')) as f:
            assert f.read() == '# updated stub'

        real_path = get_default_documents_path()
        assert os.path.isdir(real_path), 'get_default_documents_path() returned a non-existent path'
        print('Detected Documents folder:', real_path)

    print('wizard_logic: all checks passed')
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `python installer/wizard_logic.py`
Expected: `NotImplementedError` from `get_default_documents_path()` (called indirectly, but since `install()` is also a stub, you'll actually hit whichever runs first — both should raise `NotImplementedError`).

- [ ] **Step 3: Implement `get_default_documents_path` and `install`**

Replace the two `raise NotImplementedError` bodies:

```python
def get_default_documents_path():
    """Real Documents folder path, resolving OneDrive Known Folder Move
    redirection via the Windows Known Folder API — more reliable than
    assuming %USERPROFILE%\\Documents."""
    try:
        guid = _GUID.from_buffer_copy(uuid.UUID(FOLDERID_DOCUMENTS).bytes_le)
        path_ptr = ctypes.c_wchar_p()
        hresult = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, 0, ctypes.byref(path_ptr))
        if hresult == 0:
            path = path_ptr.value
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)
            return path
    except Exception:
        pass
    return os.path.join(os.path.expanduser('~'), 'Documents')
```

```python
def install(source_dir, remote_scripts_path):
    """Copy source_dir (the AbletonDiscordPresence folder) into
    remote_scripts_path, creating it if needed and overwriting any
    existing install. Returns the final destination path."""
    os.makedirs(remote_scripts_path, exist_ok=True)
    dest = os.path.join(remote_scripts_path, SCRIPT_FOLDER_NAME)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    shutil.copytree(source_dir, dest)
    return dest
```

- [ ] **Step 4: Run it again, confirm it passes**

Run: `python installer/wizard_logic.py`
Expected: prints the real detected Documents path followed by `wizard_logic: all checks passed`, exit code 0. Confirm the printed path is your actual Documents folder (or its OneDrive redirection target, if applicable).

- [ ] **Step 5: Commit**

```bash
git add installer/wizard_logic.py
git commit -m "Add pure installer logic: Documents detection, copy/update"
```

---

### Task 4: `installer/setup_wizard.py` — tkinter Next/Back/Finish GUI

**Files:**
- Create: `installer/setup_wizard.py`

**Interfaces:**
- Consumes: `get_remote_scripts_path`, `is_existing_install`, `install` from Task 3's `installer/wizard_logic.py`.

- [ ] **Step 1: Write the file**

```python
"""Next/Back/Finish installer GUI for AbletonDiscordPresence. Pure UI
wiring — all path/copy logic lives in wizard_logic.py so that logic can
be tested without spinning up tkinter (see wizard_logic.py's __main__)."""
import os
import sys
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from wizard_logic import get_remote_scripts_path, install, is_existing_install

TUTORIAL_URL = 'https://github.com/DA0806/Ableton-Discord-Presence/blob/master/docs/tutorial.md'


def _bundled_source_dir():
    """Path to the AbletonDiscordPresence folder to copy — inside the
    PyInstaller onefile bundle when frozen, next to this script otherwise."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'AbletonDiscordPresence')


class Wizard(tk.Tk):
    PAGES = ('welcome', 'location', 'install', 'finish')

    def __init__(self):
        tk.Tk.__init__(self)
        self.title('AbletonDiscordPresence Setup')
        self.geometry('480x320')
        self.resizable(False, False)

        self.dest_path = tk.StringVar(value=get_remote_scripts_path())
        self.open_tutorial = tk.BooleanVar(value=True)
        self.page_index = 0

        self.body = tk.Frame(self)
        self.body.pack(fill='both', expand=True, padx=16, pady=16)

        nav = tk.Frame(self)
        nav.pack(fill='x', padx=16, pady=(0, 16))
        self.back_btn = ttk.Button(nav, text='< Back', command=self._go_back)
        self.back_btn.pack(side='left')
        self.next_btn = ttk.Button(nav, text='Next >', command=self._go_next)
        self.next_btn.pack(side='right')

        self._render_page()

    def _clear_body(self):
        for widget in self.body.winfo_children():
            widget.destroy()

    def _render_page(self):
        self._clear_body()
        page = self.PAGES[self.page_index]
        getattr(self, '_render_' + page)()
        self.back_btn.config(state='normal' if self.page_index > 0 else 'disabled')
        self.next_btn.config(text='Finish' if page == 'finish' else 'Next >')

    def _render_welcome(self):
        tk.Label(self.body, text='AbletonDiscordPresence Setup', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        tk.Label(
            self.body, wraplength=440, justify='left',
            text=('This installs the AbletonDiscordPresence Remote Script '
                  'into your Ableton Live User Library, so your Discord '
                  'status shows your project name, BPM, and scale.'),
        ).pack(anchor='w', pady=(12, 0))

    def _render_location(self):
        tk.Label(self.body, text='Install location', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        tk.Label(
            self.body, wraplength=440, justify='left',
            text='Detected Ableton Remote Scripts folder:',
        ).pack(anchor='w', pady=(12, 4))
        row = tk.Frame(self.body)
        row.pack(fill='x')
        tk.Entry(row, textvariable=self.dest_path).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Browse...', command=self._browse).pack(side='left', padx=(8, 0))

    def _render_install(self):
        tk.Label(self.body, text='Install', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        if is_existing_install(self.dest_path.get()):
            msg = 'Previous installation detected — it will be updated.'
        else:
            msg = 'AbletonDiscordPresence will be installed to the folder above.'
        tk.Label(self.body, wraplength=440, justify='left', text=msg).pack(anchor='w', pady=(12, 0))

    def _render_finish(self):
        tk.Label(self.body, text='Done', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        tk.Label(
            self.body, wraplength=440, justify='left',
            text=('Restart Ableton Live, then go to Preferences -> Link, '
                  'Tempo & MIDI and select "AbletonDiscordPresence" in a '
                  'Control Surface dropdown.'),
        ).pack(anchor='w', pady=(12, 12))
        tk.Checkbutton(self.body, text='Open the setup tutorial', variable=self.open_tutorial).pack(anchor='w')

    def _browse(self):
        chosen = filedialog.askdirectory(initialdir=self.dest_path.get())
        if chosen:
            self.dest_path.set(chosen)

    def _go_back(self):
        self.page_index -= 1
        self._render_page()

    def _go_next(self):
        page = self.PAGES[self.page_index]
        if page == 'install':
            try:
                install(_bundled_source_dir(), self.dest_path.get())
            except OSError as exc:
                messagebox.showerror('Install failed', str(exc))
                return
        if page == 'finish':
            if self.open_tutorial.get():
                webbrowser.open(TUTORIAL_URL)
            self.destroy()
            return
        self.page_index += 1
        self._render_page()


if __name__ == '__main__':
    Wizard().mainloop()
```

- [ ] **Step 2: Manual run-through (no automated GUI test — see wizard_logic.py's self-check for the logic underneath)**

When run unfrozen (`python installer/setup_wizard.py`, no `sys._MEIPASS`), `_bundled_source_dir()` resolves to `installer/AbletonDiscordPresence` — that only exists once PyInstaller bundles it (Task 5). For this manual run-through, temporarily copy the repo's `AbletonDiscordPresence/` folder into `installer/` (`cp -r AbletonDiscordPresence installer/` from the repo root, or the PowerShell equivalent `Copy-Item -Recurse AbletonDiscordPresence installer/`), then run `python installer/setup_wizard.py` from the repo root. Delete `installer/AbletonDiscordPresence/` again afterward — it's a scratch copy for this test only, not a real repo file (the `.gitignore` in Task 5 doesn't cover it, so don't commit it).

Click through Welcome → Location (confirm the detected path looks right, try Browse) → Install (confirm it copies successfully, and re-run the whole wizard once more to confirm the "Previous installation detected" message appears the second time) → Finish (confirm the tutorial checkbox opens the browser).

- [ ] **Step 3: Commit**

```bash
git add installer/setup_wizard.py
git commit -m "Add tkinter Next/Back/Finish setup wizard GUI"
```

---

### Task 5: Package the wizard as a standalone `.exe`

**Files:**
- Create: `installer/build.bat`
- Create: `.gitignore`

**Interfaces:**
- Consumes: `installer/setup_wizard.py` (Task 4) and the repo's `AbletonDiscordPresence/` folder (Tasks 1–2) as PyInstaller's `--add-data` payload.

- [ ] **Step 1: Install the build-time dependency**

Run: `pip install pyinstaller`
Expected: installs successfully. This is a dev-only tool — never a runtime dependency of the Remote Script or of the built `.exe`'s end users.

- [ ] **Step 2: Write `installer/build.bat`**

```bat
@echo off
cd /d "%~dp0"
pyinstaller --onefile --windowed --name AbletonDiscordPresenceSetup ^
    --add-data "..\AbletonDiscordPresence;AbletonDiscordPresence" ^
    setup_wizard.py
```

- [ ] **Step 3: Write `.gitignore`**

```
installer/build/
installer/dist/
installer/*.spec
installer/AbletonDiscordPresence/
__pycache__/
*.pyc
```

- [ ] **Step 4: Build and smoke-test the .exe**

Run: `installer\build.bat` (from the repo root, or double-click it in Explorer)
Expected: `installer\dist\AbletonDiscordPresenceSetup.exe` is created with no errors.

Then double-click `installer\dist\AbletonDiscordPresenceSetup.exe` directly (not via `python`) and click through all four screens against a scratch/test Remote Scripts folder (use Browse to point somewhere disposable, not your real Live install, for this smoke test) — confirm the copied `AbletonDiscordPresence` folder appears with all three `.py` files inside, proving `--add-data` bundling worked.

- [ ] **Step 5: Commit**

```bash
git add installer/build.bat .gitignore
git commit -m "Add PyInstaller packaging for the setup wizard"
```

(Do not commit `installer/build/` or `installer/dist/` — `.gitignore` excludes them. Upload the built `.exe` to a GitHub Release by hand, per README.)

---

### Task 6: `docs/tutorial.md` — in-Ableton configuration walkthrough

**Files:**
- Create: `docs/tutorial.md`

- [ ] **Step 1: Write the file**

```markdown
# Configuring AbletonDiscordPresence inside Ableton Live

This covers the last step after installing AbletonDiscordPresence (via the
setup wizard or by copying the folder manually): telling Ableton Live to
load it.

## 1. Restart Ableton Live

If Live was open during install, close it completely and reopen it — Live
only scans the Remote Scripts folder on startup.

<!-- TODO: screenshot — Ableton Live splash/startup -->

## 2. Open Preferences

Go to **Options → Preferences** and select the **Link, Tempo & MIDI** tab.

<!-- TODO: screenshot — Preferences menu location -->

## 3. Select the Control Surface

In the **Control Surface** section, click any empty slot's dropdown and
choose **AbletonDiscordPresence** from the list.

<!-- TODO: screenshot — Control Surface dropdown with AbletonDiscordPresence selected -->

## 4. Confirm it's running

Open or save a project. Within a few seconds your Discord profile should
show:

- **Project:** your set's name (or "Undefined" until you save it once)
- **BPM:** the current tempo, plus the scale if you've turned on Scale
  Awareness (Live 12+) for that project

<!-- TODO: screenshot — Discord profile showing the Rich Presence -->

## Troubleshooting

If nothing shows up, see the *Troubleshooting* section in the main
[README](../README.md) — it covers the most common causes (Discord not
running, `Log.txt` diagnostics, and how to run the standalone smoke test).
```

- [ ] **Step 2: Commit**

```bash
git add docs/tutorial.md
git commit -m "Add dedicated in-Ableton configuration tutorial"
```

(Real screenshots replace the `<!-- TODO -->` markers later — out of scope for this plan, see design doc's Feature 3b note.)

---

### Task 7: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the full file contents**

```markdown
# Ableton Live → Discord Rich Presence

Shows your Ableton Live project (name, BPM, and scale on Live 12+) as
Discord Rich Presence. Runs entirely inside Ableton — no separate app to
keep running.

**Windows only.** `discord_ipc.py` talks to Discord over a Windows named
pipe (`\\.\pipe\discord-ipc-N`); macOS/Linux use a different IPC mechanism
that this script doesn't implement.

## Quick install

Download `AbletonDiscordPresenceSetup.exe` from the
[latest Release](https://github.com/DA0806/Ableton-Discord-Presence/releases/latest),
run it, and follow the wizard — it detects your Ableton Remote Scripts
folder (handling OneDrive-redirected Documents folders) and installs
AbletonDiscordPresence for you. No Discord setup needed on your end; the
project uses one shared Discord Application for everyone.

Then see [`docs/tutorial.md`](docs/tutorial.md) for the one-time step of
telling Ableton Live to load it.

## Manual install

If you'd rather not run a downloaded `.exe`, or the wizard doesn't find
your setup:

1. Copy the entire `AbletonDiscordPresence` folder into Ableton Live's
   User Library Remote Scripts directory:
   `%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\`
   (create the `Remote Scripts` folder if it doesn't exist yet — note: if
   your Documents folder is redirected by OneDrive, use the actual target
   of that redirection, e.g. `...\OneDrive\Documents\Ableton\...`).
2. Follow [`docs/tutorial.md`](docs/tutorial.md) to enable it inside Live.

**Why the folder name matters:** Ableton Live loads a Remote Script by
running `import <folder name>` internally — the folder name must be a
valid Python identifier. A name with spaces causes Live to fail with
`SyntaxError: invalid syntax` in `Log.txt` (Help menu → Show Log File),
and the control surface silently does nothing when selected. Always use
a space-free folder name like `AbletonDiscordPresence`.

## Notes

- An unsaved project shows as "Undefined" until you save it once (Ableton
  only assigns a name on save).
- Scale only appears in Discord when you've turned on Scale Awareness
  (Live 12+) for that project — otherwise Discord just shows BPM.
- If Discord isn't running yet when Live starts, the script keeps retrying
  in the background — no manual reconnect needed.

## Troubleshooting

If Rich Presence never appears, check:

1. **Ableton's `Log.txt`** (Help menu → Show Log File) for
   `AbletonDiscordPresence:` lines — the script logs the result of
   `connect()` every time it starts.
2. **Discord desktop app is running and you're logged in.**
3. **The Control Surface is actually selected** — Preferences → Link,
   Tempo & MIDI → Control Surface dropdown, see `docs/tutorial.md`.

To isolate whether the problem is Discord-side or Ableton-side, run the
standalone smoke test outside of Ableton (with Discord running):

```
python AbletonDiscordPresence/discord_ipc.py 1531793691486716096 ableton_logo
```

If that shows Rich Presence correctly, the issue is specific to how Live
is loading/running the script; if it doesn't, the issue is Discord itself
(not running, not logged in, or a firewall blocking the local pipe).
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Document Quick install wizard and drop the Client ID setup step"
```

---

### Task 8: Final end-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Fresh-install path**

On a machine/folder without an existing `AbletonDiscordPresence` install, run the built `.exe`, confirm the Install screen reads "AbletonDiscordPresence will be installed..." (not the "previous installation" message), finish the wizard, restart Live, and confirm Rich Presence appears per `docs/tutorial.md`.

- [ ] **Step 2: Update path**

Run the same `.exe` again against the same destination. Confirm the Install screen now reads "Previous installation detected — it will be updated," and that Live still works correctly afterward (restart Live once more).

- [ ] **Step 3: Scale on/off in Live 12**

With the set open, toggle Scale Awareness on, change key and scale a couple of times, confirm Discord's BPM line updates live each time with the correct note name and scale name; toggle it off and confirm the scale text disappears within ~5s.

- [ ] **Step 4: Pre-Live-12 fallback (if available)**

Open the same script on a Live <12 install (or temporarily monkey-patch `hasattr` mentally by reasoning through the code — real hardware/version testing is preferred if you have access). Confirm no error in `Log.txt` and Discord shows plain `BPM: <n>`.

- [ ] **Step 5: Update memory**

Save an engram observation (type `decision` or `discovery`) summarizing anything that differed from the design doc during implementation (e.g., if the OneDrive detection needed adjustment on your actual machine, or the wizard needed a layout tweak) — future sessions should know if reality diverged from the plan.
