"""Local adapters: only a filesystem `FormStore`, for the forms registry.

Job storage (repository, queue, result store, notifications) has no local
adapter any more - it is always Azure (see
`partikkelspredning.composition.build_job_service`). `form_store.py`'s
`LocalFormStore` requires no cloud credentials and is used for local
development and the default test suite's coverage of the multiple-forms
registry (`partikkelspredning.composition.build_forms_store`).
"""
