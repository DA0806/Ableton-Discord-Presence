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
        self.connected = False
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
