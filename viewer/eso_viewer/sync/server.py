"""Client for the standalone FastAPI sync server (source now also checked
into this project at ../../eso-sync-server/, cloned off `server` for
reference/redeploy -- the live copy on that box's Docker container is what
actually serves requests, this client always talks to that over the network).
Restores "Sync Server" as a second Save file source (see settings_dialog.py)
alongside "This PC": instead of parsing a local ESOHelper.lua, fetch_all()
pulls whatever's already been pushed to the server's /characters,
/achievements, /set-collections endpoints.

push_all() is the producer side, for a "This PC" machine (zeus) that also
wants other machines' "Sync Server" mode to see fresh data -- see
settings_dialog.py's "Also push this PC's data to the Sync Server" checkbox
and main.py's _reload(). Restored 2026-09-17; between 2026-07-15 (the
many-producers retirement) and then, nothing pushed here at all. The server's
own bulk-upsert endpoints (see ../../eso-sync-server/app.py) already do
last_updated-based staleness rejection and, for characters, a field-level
merge -- both written for the original many-producers-through-a-server model
-- so pushing from here needed no server-side changes, just a client.

base_url/token are read from the same ~/.config/eso-helper/sync.json used for
remote_dir (see eso_viewer/sync/config.py) -- kept out of source for the same
reason that is. The server currently has no auth configured (private LAN,
doesn't need to be secure), so token can be left unset.
"""
from __future__ import annotations

import dataclasses

import requests

_TIMEOUT = 8


class SyncServerError(Exception):
    pass


def _get(base_url: str, token: str | None, path: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = requests.get(f"{base_url.rstrip('/')}{path}", headers=headers, timeout=_TIMEOUT)
    except requests.RequestException as e:
        raise SyncServerError(str(e)) from e
    if resp.status_code != 200:
        raise SyncServerError(f"{path} returned {resp.status_code}")
    return resp.json()


def _put(base_url: str, token: str | None, path: str, payload: dict) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = requests.put(
            f"{base_url.rstrip('/')}{path}", json=payload, headers=headers, timeout=_TIMEOUT
        )
    except requests.RequestException as e:
        raise SyncServerError(str(e)) from e
    if resp.status_code != 200:
        raise SyncServerError(f"{path} returned {resp.status_code}")
    return resp.json()


def fetch_all(base_url: str, token: str | None = None) -> dict[str, list[dict]]:
    """Pull the server's full characters/achievements/set-collections snapshot.
    Raises SyncServerError on any failure -- callers should catch this and fall
    back the same way a missing sync.json already does."""
    return {
        "characters": _get(base_url, token, "/characters"),
        "achievements": _get(base_url, token, "/achievements"),
        "set_collections": _get(base_url, token, "/set-collections"),
    }


def push_all(
    base_url: str,
    token: str | None,
    characters: list,
    achievements: list,
    set_collections: list,
) -> None:
    """Push a freshly-parsed local snapshot up to the sync server.
    `dataclasses.asdict()` on each model object matches exactly what
    model.py's character_from_dict/achievements_from_dict/
    set_collections_from_dict expect back out the other end when some other
    machine later GETs this same data in "Sync Server" mode. Raises
    SyncServerError on any failure -- callers should catch this and just log
    it, since a failed push shouldn't block this machine's own local reload
    from succeeding."""
    _put(base_url, token, "/characters/bulk",
         {"characters": [dataclasses.asdict(c) for c in characters]})
    _put(base_url, token, "/achievements/bulk",
         {"achievements": [dataclasses.asdict(a) for a in achievements]})
    _put(base_url, token, "/set-collections/bulk",
         {"set_collections": [dataclasses.asdict(s) for s in set_collections]})
