"""Ports: the interfaces business logic depends on, implemented by adapters.

Each port is a small `Protocol` describing one capability the domain/service
layer needs (persisting jobs, distributing work, resolving results,
notifying users, storing rendered forms). Job storage is implemented only
by `partikkelspredning.adapters.azure` (always required - no local mode);
`FormStore` is implemented by both `partikkelspredning.adapters.local` and
`partikkelspredning.adapters.azure`. `partikkelspredning.composition` picks
between them at startup.
"""
