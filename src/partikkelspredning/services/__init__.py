"""Application services: orchestrate domain objects and ports.

Nothing under `partikkelspredning.services` imports `azure`, `pandas`, or
`fastapi` directly - it only knows about the `Protocol`s in
`partikkelspredning.ports`. Which concrete adapters are plugged in is
decided once, at startup, by `partikkelspredning.composition`.
"""
