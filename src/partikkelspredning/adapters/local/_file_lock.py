"""A tiny cross-process advisory lock used by the local CSV adapters.

This exists purely so that concurrent local processes/threads touching the
same file behave predictably in tests and simple local use - it is not
meant to scale beyond that. See `csv_repository` and `csv_queue` for why a
production deployment uses Azure Table Storage / Storage Queue instead,
which provide their own real concurrency guarantees.

Uses `fcntl.flock`, so this only works on POSIX systems (Linux/macOS) - fine
for this project's deployment targets (local dev on Linux, Azure Functions'
Linux workers), but not portable to Windows.
"""
from __future__ import annotations

import contextlib
import fcntl
from pathlib import Path
from typing import Iterator, Union


@contextlib.contextmanager
def locked(lock_path: Union[Path, str]) -> Iterator[None]:
    """Hold an exclusive, blocking lock on `lock_path` for the block's duration."""
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
