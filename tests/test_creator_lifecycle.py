from datetime import datetime, timedelta, timezone

from src.creator_lifecycle import expired_keys, should_expire


def test_throwaway_creator_object_expires_after_ttl():
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    items = [
        {"key": "creator-a/preview.mp4", "created_at": "2026-01-01T00:00:00Z"},
        {"key": "creator-a/final.mp4", "created_at": "2026-01-01T12:00:00Z"},
    ]

    assert should_expire(now - timedelta(hours=25), now, timedelta(hours=24))
    assert expired_keys(items, now, timedelta(hours=24)) == ["creator-a/preview.mp4"]
