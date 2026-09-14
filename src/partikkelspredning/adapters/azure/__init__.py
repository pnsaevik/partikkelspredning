"""Azure adapters: Table Storage, Storage Queue, Blob Storage.

Together with `api/function_app.py`, this package is the only place in the
project allowed to import `azure.*` (see the root README's "Vendor
independence" section). Nothing here is imported unless
`PARTIKKEL_STORAGE_MODE=azure` is selected - see
`partikkelspredning.composition.build_job_service` - so the Azure SDKs are
not required for local development or the default test suite.
"""
