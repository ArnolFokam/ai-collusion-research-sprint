"""Full record of every model call in a run: request, raw response, errors, retries.

One JSON object per line, gzip-compressed. Flushed after each call, so a crashed run still
leaves a readable transcript.
"""
from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from typing import Iterator


class Transcript:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._f = gzip.open(self.path, "wt", encoding="utf-8")
        self._t0 = time.time()

    def log(self, **entry) -> None:
        entry["t"] = round(time.time() - self._t0, 3)   # seconds since the run started
        self._f.write(json.dumps(entry, default=str) + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> "Transcript":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def read(path: Path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)
