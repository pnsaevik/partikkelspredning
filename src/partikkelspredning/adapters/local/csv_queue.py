"""Local `JobQueue` backed by a plain-text file, one job id per line.

`try_claim` pops the first line under an exclusive file lock, which is
sufficient to guarantee two local callers never claim the same job id - see
`partikkelspredning.ports.queue.JobQueue` for why that guarantee is what
matters here. This is a plain FIFO queue with no visibility timeout: unlike
the Azure Storage Queue adapter, a claimed id is simply gone from this file.
Recovering a claim whose worker disappeared is left to the future
lease/retry mechanism described in the root README.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from partikkelspredning.adapters.local._file_lock import locked


class CsvJobQueue:
    def __init__(self, queue_path: Union[Path, str]) -> None:
        self._path = Path(queue_path)
        self._lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("")

    def enqueue(self, job_id: str) -> None:
        with locked(self._lock_path):
            with open(self._path, "a") as f:
                f.write(job_id + "\n")

    def try_claim(self) -> Optional[str]:
        with locked(self._lock_path):
            lines = [line for line in self._path.read_text().splitlines() if line]
            if not lines:
                return None
            job_id, *rest = lines
            self._path.write_text("\n".join(rest) + ("\n" if rest else ""))
            return job_id
