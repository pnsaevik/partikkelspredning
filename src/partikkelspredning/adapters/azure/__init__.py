"""Azure adapters: Table Storage, Storage Queue, Blob Storage.

Together with `api/function_app.py`, this package is the only place in the
project allowed to import `azure.*` (see the root README's "Vendor
independence" section). Job storage
(`partikkelspredning.composition.build_job_service`) always uses these
adapters - there is no local mode for it. `BlobFormStore` here is also used
by `build_forms_store`/`build_form_store` whenever `PARTIKKEL_STORAGE_MODE`
selects Azure for forms storage; the Azure SDKs are otherwise not required
for the default test suite (which uses `tests/fakes.py` and
`adapters.local.form_store.LocalFormStore` instead).
"""
