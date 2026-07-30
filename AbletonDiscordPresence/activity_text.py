"""Pure Discord Rich Presence text formatting for AbletonDiscordPresence.
No Live/_Framework dependency — importable and testable outside Ableton,
unlike presence.py which requires _Framework.ControlSurface."""

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
UNDEFINED_NAME = 'Undefined'


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
