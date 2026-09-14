"""Port: turns a compute worker's result reference into a URL a user can open.

The (not yet implemented) compute server is expected to write its output
somewhere the configured `ResultStore` adapter knows about, and report back
a `result_reference` - an adapter-specific identifier (a local file path, a
blob name, ...) - when calling the job-completion endpoint.
`build_result_url` turns that reference into the URL included in the
completion notification and the job's API representation.
"""
from __future__ import annotations

from typing import Protocol


class ResultStore(Protocol):
    def build_result_url(self, job_id: str, result_reference: str) -> str:
        """Resolve `result_reference` (for `job_id`) to a URL a user can open."""
