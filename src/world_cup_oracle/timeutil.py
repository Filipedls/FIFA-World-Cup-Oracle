"""Timezone-aware formatting of kickoff times.

Kickoff strings come from different sources: API providers give tz-aware UTC
ISO timestamps; worldcup26 gives a naive local string. Naive timestamps are
assumed to be UTC so conversion is consistent and well-defined.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_UTC = ZoneInfo("UTC")


def _zone(tzname: str) -> ZoneInfo:
    try:
        return ZoneInfo(tzname)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return _UTC


def to_timezone(kickoff_iso: str | None, tzname: str) -> datetime | None:
    if not kickoff_iso:
        return None
    try:
        dt = datetime.fromisoformat(kickoff_iso)
    except ValueError:
        return None
    if dt.tzinfo is None:          # naive -> assume the source meant UTC
        dt = dt.replace(tzinfo=_UTC)
    return dt.astimezone(_zone(tzname))


def format_kickoff(kickoff_iso: str | None, tzname: str, fallback: str = "") -> str:
    dt = to_timezone(kickoff_iso, tzname)
    if dt is None:
        return fallback
    return dt.strftime("%a %d %b · %H:%M %Z")
