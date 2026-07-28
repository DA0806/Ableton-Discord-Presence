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
