"""Placeholder authentication hook for compute-server endpoints.

`require_worker_auth` currently allows every request through - the
prototype intentionally does not implement authentication yet (see the root
README's Security section) - but every endpoint the future compute server
calls (`claim`, `complete`, `fail`) already depends on it, so adding real
authentication (an API key, mTLS, ...) later means changing only this one
function, not every route.
"""
from __future__ import annotations


def require_worker_auth() -> None:
    """TODO: verify the caller is an authorized compute worker before production use."""
    return None
