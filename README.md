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
