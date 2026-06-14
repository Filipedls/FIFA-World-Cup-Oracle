"""Test-wide setup: keep the suite offline and deterministic.

These must run before the package is imported (config reads env at import time),
so they live at module top-level in conftest. ``setdefault`` means a real env
var still wins if you deliberately set one.
"""
import os
import tempfile

# Unknown source -> loader falls back to the offline sample (no network calls).
os.environ.setdefault("WORLD_CUP_DATA_SOURCE", "sample-test")
# Isolate the disk cache so a real local .cache can't leak into tests.
os.environ.setdefault("WORLD_CUP_CACHE_DIR", tempfile.mkdtemp(prefix="wc_test_cache_"))
# Make sure no stray odds key triggers a network enrichment.
os.environ.pop("THE_ODDS_API_KEY", None)
