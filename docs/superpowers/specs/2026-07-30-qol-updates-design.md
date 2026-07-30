# QoL Updates: labeled fields, scale display, setup wizard — Design

## Problem

The Remote Script works and is manually installable. Three quality-of-life gaps remain:

1. Discord shows the raw project name and `"120 BPM"` — no labels, so it's not obvious at a glance what the two lines mean.
2. Ableton Live 12 added Scale Awareness (root note + scale name) to the Live Object Model, but the script doesn't surface it.
3. Install is fully manual (copy folder, edit `presence.py` by hand) — fine for the author, friction for anyone else.

## Scope

All three are small, independent changes to the same project, done together as one round of polish:

1. Label the two Discord Rich Presence lines.
2. Show the project's scale on Live 12+ when the user has actually turned Scale Awareness on, with a clean fallback on older Live versions.
3. A double-click `.exe` installer wizard (Next/Back/Finish) that detects the Remote Scripts folder, installs/updates the script, and points to a written tutorial.

## Feature 1: Labeled Rich Presence fields

Change in `presence.py::_push_activity`:

- `details` = `"Project: %s" % name` (was `name`)
- `state` = `"BPM: %d" % bpm` (was `"%d BPM" % bpm`) — extended in Feature 2 below.

No other behavior changes; `UNDEFINED_NAME` fallback for unsaved projects is untouched.

## Feature 2: Scale display (Live 12+, opt-in)

Live 12's LOM adds `Song.root_note` (int 0–11, 0=C), `Song.scale_name` (str, e.g. `"Major"`), and `Song.scale_mode` (bool — the actual "Scale Awareness is on for this project" toggle the user sees in Live's UI). These don't exist as attributes on `Song` in Live ≤11.

- **When to show it:** only when `song.scale_mode` is `True`. `scale_name`/`root_note` always hold *some* value (Live's default is `"C"`/`"Major"`) even when the user never touched the feature, so gating on `scale_mode` avoids showing a meaningless default on every project.
- **Where:** appended to the same `state` line as BPM, since Discord Rich Presence only has two text lines (`details`, `state`) and there's no natural third slot:
  `state = "BPM: %d · %s %s" % (bpm, note_name, scale_name)` → e.g. `"BPM: 120 · C Major"`.
  Without scale (Live <12, or `scale_mode` off): `state = "BPM: %d" % bpm`, unchanged from Feature 1.
- **Note naming:** fixed sharps table, index by `root_note`: `['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']`. Matches Ableton's own default display.
- **Fallback / version detection:** `hasattr(song, 'scale_mode')` — Live <12 never has the attribute, so the check short-circuits and behavior is identical to Feature 1 with zero risk of `AttributeError`.
- **Live updates:** register `add_scale_name_listener`, `add_root_note_listener`, `add_scale_mode_listener` on `song` (same pattern as the existing `add_tempo_listener`), each calling `_push_activity`, and removed in `disconnect()` alongside the tempo listener. Guard registration with the same `hasattr` check (older Live has no `add_scale_mode_listener` etc. either).

## Feature 3: Setup wizard

### Scope decision

The wizard only replaces the *installation* half of setup (copy files to the right place). Creating the Discord Application and uploading the art asset stays manual and out of the wizard's scope — but it also stops being something end users need to do at all:

**The Discord Client ID becomes a fixed, shared value hardcoded into the `presence.py` that ships in the repo/installer**, owned by the project maintainer (same pattern VS Code / Spotify Rich Presence integrations use — Discord's IPC doesn't require the connecting process to own the Application, so one shared Client ID works for every installer). End users never see a Client ID field. The maintainer still does the one-time Developer Portal setup (create app, upload `ableton_logo` asset) for themselves, same as today, just no longer per-installer.

This means `presence.py`'s `DISCORD_CLIENT_ID` in git moves from the `'REPLACE_WITH_YOUR_DISCORD_CLIENT_ID'` placeholder to the maintainer's real Application ID, committed as-is. A Discord Client ID is a public identifier (like an OAuth client ID) — Rich Presence's IPC handshake never uses a client secret, so committing it publicly is standard practice, not a credential leak. The README's "replace the placeholder" step goes away entirely.

### Wizard flow (tkinter, Next/Back/Finish)

New `installer/setup_wizard.py`, separate from `AbletonDiscordPresence/` (the Remote Script itself is untouched by this feature beyond Features 1–2).

1. **Welcome** — one paragraph on what the installer does.
2. **Location** — auto-detects the real `Documents` folder via `SHGetKnownFolderPath` (Windows API through `ctypes`, resolves OneDrive Known Folder Move redirection correctly — more reliable than assuming `%USERPROFILE%\Documents`), then appends `Ableton\User Library\Remote Scripts`. Shows the detected path with a "Browse..." button to override.
3. **Install** — before copying, checks whether `Remote Scripts\AbletonDiscordPresence\` already exists:
   - If yes: screen reads "Previous installation detected — it will be updated" instead of the generic "will be installed" text.
   - If no: creates `Remote Scripts\` if missing, then either way copies (overwrites) the bundled `AbletonDiscordPresence` folder into place.
4. **Finish** — confirms success, reminds the user to restart Ableton Live and enable "AbletonDiscordPresence" under Preferences → Link, Tempo & MIDI → Control Surface. Includes a checkbox, **checked by default**, "Open the setup tutorial" — on clicking Finish, if checked, opens the default browser to the new tutorial doc (Feature 3b below) on GitHub.

### Packaging

`PyInstaller --onefile --windowed`, with the `AbletonDiscordPresence/` source folder embedded via `--add-data` so the compiled `.exe` is fully standalone (end user needs no Python at all). Built locally by the maintainer and attached to a GitHub Release; no CI build pipeline as part of this work.

### Feature 3b: Separate tutorial doc

New `docs/tutorial.md` (repo root `docs/`, not `docs/superpowers/`) — a dedicated, image-illustrated walkthrough of the in-Ableton configuration steps (Preferences → Link, Tempo & MIDI → Control Surface dropdown → select AbletonDiscordPresence → confirm it's live). This content currently lives as README steps 2–4; it moves/expands into this doc instead of duplicating.

- README's Install section is trimmed to the copy/build step and gets a link to `docs/tutorial.md` for the in-Ableton part, plus a new "Quick install" callout pointing at the `.exe` from GitHub Releases as an alternative to manual copying.
- **Assumption/handoff:** I write the tutorial's text content; the actual Ableton screenshots need to be supplied by the user (I have no way to capture live screenshots of their Ableton install) — the doc ships with clearly marked image placeholders until real screenshots are dropped in.

## Error handling

- Wizard: any failure to create/write in the detected Remote Scripts path (permissions, path doesn't exist and can't be created) shows an error dialog on the Install screen with the exception message, and does not advance to Finish — user can Back up and pick a different path via Browse.
- `SHGetKnownFolderPath` failure (should be near-impossible on any real Windows install) falls back to `%USERPROFILE%\Documents` and lets the user confirm/override on the Location screen rather than crashing the wizard.
- Scale listeners follow the existing `_push_activity` try/except — any LOM access failure is swallowed, same as today, never propagates into Live.

## Testing

- `presence.py` changes: no in-Live test runner exists (per the original design doc); verify manually by opening a Live 12 set, toggling Scale Awareness on/off, changing key/scale, and confirming the Discord state line updates live. Verify Live <12 (or `scale_mode` unset) shows the plain `BPM: ###` line with no error in `Log.txt`.
- Wizard: manual run of the compiled `.exe` on a clean-ish machine/VM if available; at minimum, run against both an OneDrive-redirected Documents folder and a non-redirected one, and against both a fresh install and an "update existing install" pass, confirming the correct Install-screen message in each case.

## Explicitly out of scope

- Automating Discord Application creation / art asset upload — no public API for this that fits a personal tool; stays a one-time manual maintainer step.
- macOS/Linux support (unchanged from original design — Windows-only IPC).
- CI-built/signed installer, auto-update mechanism for the wizard itself.
- Any Rich Presence fields beyond project/BPM/scale (buttons, party size, play/pause glyph) — still deferred per the original design doc.
