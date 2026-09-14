"""Local adapters: CSV files, the filesystem, and the console.

Used for local development and the default test suite. None of these
require any cloud credentials. They are intentionally simple - see each
module's docstring - and are not meant to become a production persistence
layer; that's what `partikkelspredning.adapters.azure` is for.
"""
