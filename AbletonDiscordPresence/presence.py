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
