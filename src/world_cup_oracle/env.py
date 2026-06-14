"""Load a project-root `.env` into ``os.environ`` before config reads it.

Kept dependency-free (no python-dotenv) and idempotent: it uses ``setdefault``,
so real environment variables always win over the file and repeated calls are
harmless.
"""
from __future__ import annotations

import os
from pathlib import Path

_loaded = False


def load_dotenv() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    candidates = (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env")
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))
