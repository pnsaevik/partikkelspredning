"""Platform-agnostic business logic: job state, parameters, and errors.

Nothing under `partikkelspredning.domain` may import `azure`, `pandas`, or
`fastapi` - see the root README's "Vendor independence" section. This is
what lets the domain be unit-tested with no infrastructure at all, and lets
every adapter (local CSV files, Azure Table/Queue/Blob Storage, ...) be
swapped without touching it.
"""
