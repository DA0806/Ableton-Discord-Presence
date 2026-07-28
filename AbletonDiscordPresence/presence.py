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
