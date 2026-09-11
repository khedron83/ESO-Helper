"""Per-account bank gold snapshots, used to compute a 24h gold-gained delta on the Bank
tab. Gold has no history anywhere else (server/local DB only ever hold the current
value), so this keeps its own small append-only log, following the same plain-JSON
state-file pattern as sync/addon.py's addon_sync_state.json.
"""
import datetime
import json
from pathlib import Path

_HISTORY_FILE = Path.home() / '.local/share/eso-helper/gold_history.json'
# Pre-rename path (this app was "ESO Build Manager"). Read as a one-time
# migration source if the new file doesn't exist yet; never written to.
_LEGACY_HISTORY_FILE = Path.home() / '.local/share/eso-build-manager/gold_history.json'
_MAX_AGE_SECONDS = 7 * 24 * 3600  # a week of samples is plenty for a 24h lookback
_RESET_HOUR_UTC = 11  # ESO's daily server reset


def _last_reset(now: int) -> int:
    """Timestamp of the most recent ESO daily reset (11:00 UTC) at or before `now`."""
    dt = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc)
    reset = dt.replace(hour=_RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    if dt < reset:
        reset -= datetime.timedelta(days=1)
    return int(reset.timestamp())


def _load() -> dict[str, list[list[int]]]:
    for path in (_HISTORY_FILE, _LEGACY_HISTORY_FILE):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                return {}
    return {}


def _save(history: dict[str, list[list[int]]]) -> None:
    _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_FILE.write_text(json.dumps(history))


def record_snapshot(account_gold: dict[str, int], now: int) -> None:
    """Append a [timestamp, gold] sample per account, pruning samples older than a week."""
    history = _load()
    cutoff = now - _MAX_AGE_SECONDS
    for account, gold in account_gold.items():
        samples = [s for s in history.get(account, []) if s[0] >= cutoff]
        samples.append([now, gold])
        history[account] = samples
    _save(history)


def gold_gained(account: str, now: int) -> tuple[int, int] | None:
    """Gold gained (negative if lost) for an account since the most recent ESO daily
    reset (11:00 UTC) -- or, if we don't have samples back that far yet, the oldest
    sample we've got, so the UI shows a real (if short-window) delta instead of
    "gathering data" right after reset. A fixed reset point (rather than a rolling
    24h-ago lookback) avoids the window silently sliding across a same-day gold spike
    (e.g. a pending trader sale) and flashing a bogus swing as it slides past it.
    Returns (delta, window_seconds actually covered), or None if there's only one
    sample so far."""
    samples = _load().get(account, [])
    if len(samples) < 2:
        return None
    reset_ts = _last_reset(now)
    baseline_ts, baseline_gold = samples[0]
    for ts, gold in samples:
        if ts <= reset_ts:
            baseline_ts, baseline_gold = ts, gold
        else:
            break
    return samples[-1][1] - baseline_gold, now - baseline_ts
