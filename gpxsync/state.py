"""A state.txt of the feed: sequenceNumber and timestamp."""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class State:
    sequence: int
    timestamp: datetime | None

    @classmethod
    def parse(cls, text: str) -> "State":
        values = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            values[key] = value.replace("\\", "")
        timestamp = values.get("timestamp")
        return cls(int(values["sequenceNumber"]), parse_time(timestamp) if timestamp else None)


def parse_time(text: str) -> datetime:
    """2026-10-19T14:22:10Z as an aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
