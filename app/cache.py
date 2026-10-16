"""Read-through cache for derived data, keyed by the database's data version.

Every write that changes what screens show bumps `meta.data_version` (db.bump_version), so a cached value is
reused only while the data it was computed from is unchanged. The version lives in the database, so several app
processes stay correct without sharing memory. Concurrent requests for the same missing value wait for one
computation instead of all running it.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Callable

from . import db


class VersionedCache:
    def __init__(self, max_entries: int = 512) -> None:
        self._data: OrderedDict[tuple, object] = OrderedDict()
        self._max = max_entries
        self._lock = threading.Lock()
        self._inflight: dict[tuple, threading.Lock] = {}
        self.hits = self.misses = 0

    def get(self, conn, namespace: str, key, compute: Callable[[], object]):
        """Value for (namespace, key) at the current data version, computing it at most once per version."""
        full = (namespace, db.data_version(conn), key)
        with self._lock:
            if full in self._data:
                self._data.move_to_end(full)
                self.hits += 1
                return self._data[full]
            gate = self._inflight.setdefault(full, threading.Lock())
        with gate:
            with self._lock:  # another request may have filled it while we waited
                if full in self._data:
                    self.hits += 1
                    return self._data[full]
            value = compute()
            with self._lock:
                self.misses += 1
                self._data[full] = value
                while len(self._data) > self._max:
                    self._data.popitem(last=False)
                self._inflight.pop(full, None)
            return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {"entries": len(self._data), "hits": self.hits, "misses": self.misses,
                    "hit_pct": round(100 * self.hits / total, 1) if total else None}


cache = VersionedCache()
