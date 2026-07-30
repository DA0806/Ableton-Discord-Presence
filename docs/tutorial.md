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
