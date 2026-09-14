"""Adapters: concrete implementations of the ports, for one platform each.

`partikkelspredning.adapters.local` requires no cloud credentials and is
used for local development and the default test suite.
`partikkelspredning.adapters.azure` is the only place (besides
`api/function_app.py`) allowed to import `azure.*`; see the root README's
"Vendor independence" section.
"""
