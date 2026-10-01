from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from typing import Protocol


class DatabaseSessionProvider(Protocol):
    """Minimal session surface for stores that must not import SQLiteRepository."""

    def connection(self) -> AbstractContextManager[sqlite3.Connection]: ...

    def transaction(self) -> AbstractContextManager[sqlite3.Connection]: ...
