"""Ports: the interfaces business logic depends on, implemented by adapters.

Each port is a small `Protocol` describing one capability the domain/service
layer needs (persisting jobs, distributing work, resolving results,
notifying users). `partikkelspredning.adapters.local` and
`partikkelspredning.adapters.azure` provide concrete implementations;
`partikkelspredning.composition` picks between them at startup.
"""
