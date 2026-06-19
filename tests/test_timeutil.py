"""Timezone conversion / formatting of kickoff times."""
from world_cup_oracle import timeutil


def test_utc_aware_converts_to_target_zone():
    # 18:00 UTC -> 13:00 New York (EDT, summer)
    dt = timeutil.to_timezone("2026-06-12T18:00:00+00:00", "America/New_York")
    assert (dt.hour, dt.minute) == (14, 0)  # EDT is UTC-4 in June


def test_naive_is_assumed_utc():
    dt = timeutil.to_timezone("2026-06-12T18:00:00", "Europe/Lisbon")
    # Lisbon is UTC+1 in June (WEST) -> 19:00
    assert dt.hour == 19


def test_format_kickoff_includes_zone_abbrev():
    s = timeutil.format_kickoff("2026-06-12T18:00:00+00:00", "UTC")
    assert "18:00" in s and "UTC" in s


def test_invalid_inputs_fall_back():
    assert timeutil.to_timezone(None, "UTC") is None
    assert timeutil.to_timezone("not-a-date", "UTC") is None
    assert timeutil.format_kickoff(None, "UTC", fallback="2026-06-12") == "2026-06-12"


def test_unknown_timezone_defaults_to_utc():
    dt = timeutil.to_timezone("2026-06-12T18:00:00+00:00", "Mars/Olympus")
    assert dt.hour == 18  # fell back to UTC
