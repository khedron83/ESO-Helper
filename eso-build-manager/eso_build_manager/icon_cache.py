"""Async skill icon fetching with disk + memory cache."""
import hashlib
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

_CACHE_DIR = Path.home() / ".local/share/eso-build-manager/icons"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_pixmap_cache: dict[str, QPixmap] = {}
_pending: dict[str, list] = {}
_manager: QNetworkAccessManager | None = None


def _mgr() -> QNetworkAccessManager:
    global _manager
    if _manager is None:
        _manager = QNetworkAccessManager()
    return _manager


def _disk_path(url: str) -> Path:
    return _CACHE_DIR / (hashlib.md5(url.encode()).hexdigest() + ".png")


def fetch_icon(url: str, callback) -> None:
    """Fetch icon and call callback(QPixmap) — returns immediately."""
    if url in _pixmap_cache:
        callback(_pixmap_cache[url])
        return

    disk = _disk_path(url)
    if disk.exists():
        px = QPixmap(str(disk))
        _pixmap_cache[url] = px
        callback(px)
        return

    if url in _pending:
        _pending[url].append(callback)
        return

    _pending[url] = [callback]

    req = QNetworkRequest(QUrl(url))
    req.setRawHeader(b"Referer", b"https://en.uesp.net/")
    req.setRawHeader(b"User-Agent", b"Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0")
    reply = _mgr().get(req)

    def _on_finished():
        callbacks = _pending.pop(url, [])
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            disk.write_bytes(bytes(data))
            px = QPixmap()
            px.loadFromData(data)
        else:
            px = QPixmap()
        _pixmap_cache[url] = px
        for cb in callbacks:
            cb(px)
        reply.deleteLater()

    reply.finished.connect(_on_finished)
