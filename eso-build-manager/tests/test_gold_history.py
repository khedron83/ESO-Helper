import datetime

from eso_build_manager.gold_history import _last_reset


def _utc(y, m, d, h, mi=0):
    return int(datetime.datetime(y, m, d, h, mi, tzinfo=datetime.timezone.utc).timestamp())


def test_last_reset_same_day_after_reset():
    now = _utc(2026, 7, 14, 23, 5)
    assert _last_reset(now) == _utc(2026, 7, 14, 11, 0)


def test_last_reset_before_todays_reset_uses_yesterday():
    now = _utc(2026, 7, 14, 3, 0)
    assert _last_reset(now) == _utc(2026, 7, 13, 11, 0)


def test_last_reset_exactly_at_boundary():
    now = _utc(2026, 7, 14, 11, 0)
    assert _last_reset(now) == now


if __name__ == '__main__':
    test_last_reset_same_day_after_reset()
    test_last_reset_before_todays_reset_uses_yesterday()
    test_last_reset_exactly_at_boundary()
    print('ok')
