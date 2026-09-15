"""Adapters: concrete implementations of the ports, for one platform each.

`partikkelspredning.adapters.local` holds only a filesystem `FormStore`
(used for local development and the default test suite's forms-registry
coverage - no cloud credentials needed). `partikkelspredning.adapters.azure`
is the only place (besides `api/function_app.py`) allowed to import
`azure.*`; see the root README's "Vendor independence" section. Job storage
(repository, queue, result store, notifications) is always Azure - see
`partikkelspredning.composition.build_job_service`.
"""
