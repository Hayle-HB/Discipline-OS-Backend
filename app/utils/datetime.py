from datetime import UTC, datetime


def ensure_utc(value: datetime) -> datetime:
    """Normalize MongoDB datetimes for safe comparison with UTC-aware values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
