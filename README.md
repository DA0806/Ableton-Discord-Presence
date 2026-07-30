# Ableton Live → Discord Rich Presence

Shows your Ableton Live project (name, BPM, time since opened) as Discord
Rich Presence. Runs entirely inside Ableton — no separate app to keep running.

**Windows only.** `discord_ipc.py` talks to Discord over a Windows named
pipe (`\\.\pipe\discord-ipc-N`); macOS/Linux use a different IPC mechanism
that this script doesn't implement.

## Setup (one-time)

1. Create a Discord Application at https://discord.com/developers/applications
   → "New Application" → name it anything (e.g. "Ableton Live").
2. Copy the **Application ID** from the General Information page.
3. In the same application, go to **Rich Presence → Art Assets**, upload a
   square PNG (512×512+) of the Ableton Live logo, and set its asset key to
   `ableton_logo`. Save. (Can take a few minutes to propagate.)
4. Open `AbletonDiscordPresence/presence.py` in this folder and replace
   `DISCORD_CLIENT_ID = 'REPLACE_WITH_YOUR_DISCORD_CLIENT_ID'` with the
   Application ID from step 2.

## Install

1. Copy the entire `AbletonDiscordPresence` folder into Ableton Live's
   User Library Remote Scripts directory:
   `%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\`
   (create the `Remote Scripts` folder if it doesn't exist yet — note: if
   your Documents folder is redirected by OneDrive, use the actual target
   of that redirection, e.g. `...\OneDrive\Documents\Ableton\...`).
2. Restart Ableton Live.
3. Open Preferences → Link, Tempo & MIDI → in the Control Surface dropdown
   (any empty slot), select "AbletonDiscordPresence".
4. Open or save a project. Your Discord profile should show the project
   name, BPM, and an elapsed-time counter within a few seconds.

**Why the folder name matters:** Ableton Live loads a Remote Script by
running `import <folder name>` internally — the folder name must be a
valid Python identifier. A name with spaces (e.g. the previous
`Ableton Discord Presence`) causes Live to fail with
`SyntaxError: invalid syntax` in `Log.txt` (Help menu → Show Log File),
and the control surface silently does nothing when selected. Always use
a space-free folder name like `AbletonDiscordPresence`.

## Notes

- An unsaved project shows as "Undefined" until you save it once (Ableton
  only assigns a name on save).
- If Discord isn't running yet when Live starts, the script keeps retrying
  in the background — no manual reconnect needed.

## Troubleshooting

If Rich Presence never appears, check:

1. **The Client ID was actually replaced** in `presence.py` — this is the
   most common cause. If `DISCORD_CLIENT_ID` is still
   `'REPLACE_WITH_YOUR_DISCORD_CLIENT_ID'`, the pipe handshake happens
   locally but Discord rejects it silently. The script logs a warning
   about this on startup (see below).
2. **Ableton's `Log.txt`** (Help menu → Show Log File) for
   `AbletonDiscordPresence:` lines — the script logs the Client ID check
   and the result of `connect()` every time it starts.
3. **Discord desktop app is running and you're logged in.**

To isolate whether the problem is Discord-side or Ableton-side, run the
standalone smoke test outside of Ableton (with Discord running):

```
python AbletonDiscordPresence/discord_ipc.py YOUR_CLIENT_ID ableton_logo
```

If that shows Rich Presence correctly, the issue is specific to how Live
is loading/running the script; if it doesn't, the issue is the Client ID,
Art Asset setup, or Discord itself.
