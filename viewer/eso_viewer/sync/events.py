"""Server-Sent Events listener for "Sync Server" mode -- replaces the plain
60s QTimer poll (see main.py's _apply_refresh_strategy()) with a push: the
server (../../../eso-sync-server/app.py's GET /events) holds one connection
per client open and writes a `data: <resource>_updated` line the instant any
/characters/bulk, /achievements/bulk, or /set-collections/bulk PUT commits,
so a remote "Sync Server" client picks up a change within seconds of zeus's
own push instead of waiting up to a minute.

Runs on its own QThread (not the Qt main/GUI thread) since the whole point is
a long-lived blocking HTTP stream (`requests.get(..., stream=True)`) -- doing
that on the GUI thread would freeze the window for as long as the connection
stays open, i.e. indefinitely. `event_received` is a Qt signal, so Qt marshals
each emit() back onto the receiver's own (GUI) thread automatically; nothing
here ever touches widgets directly.
"""
from __future__ import annotations

import requests
from PySide6.QtCore import QThread, Signal

_CONNECT_TIMEOUT = 10
_RECONNECT_DELAY_S = 5


class SyncEventListener(QThread):
    event_received = Signal(str)

    def __init__(self, base_url: str, token: str | None, parent=None):
        super().__init__(parent)
        self._base_url = base_url
        self._token = token
        self._stopping = False

    def stop(self):
        # Racy by design and harmless either way: worst case the loop below
        # reads one more line (or waits out one reconnect delay) before
        # noticing -- there's no response object kept around to close
        # out-of-band from here, since it's only ever touched inside run()'s
        # own thread.
        self._stopping = True

    def run(self):
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        url = f"{self._base_url.rstrip('/')}/events"
        while not self._stopping:
            try:
                resp = requests.get(
                    url, headers=headers, stream=True,
                    timeout=(_CONNECT_TIMEOUT, None),  # no read timeout -- this is a deliberately long-lived stream
                )
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if self._stopping:
                        break
                    if not line or line.startswith(':'):
                        continue  # blank line (SSE frame separator) or a ": keepalive" comment
                    if line.startswith('data:'):
                        self.event_received.emit(line[len('data:'):].strip())
            except requests.RequestException:
                pass  # server down/unreachable/dropped -- just retry below
            if not self._stopping:
                self.msleep(_RECONNECT_DELAY_S * 1000)
