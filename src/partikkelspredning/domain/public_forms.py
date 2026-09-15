"""Fixed parameter set for the one publicly-deployed job submission form.

See FEATURE_PLAN.md ("public_form"): a single pre-rendered form, hardcoded
for this iteration, is deployed as a standalone static HTML page (via
`partikkelspredning.services.public_form_service.deploy_public_form`) so
external users can submit a job without calling `POST /jobs` directly.
Multiple named parameter sets are a deferred future feature - see that
plan's "Future Extensibility" section.
"""
from __future__ import annotations

from partikkelspredning.domain.parameters import ParameterDefinition

PUBLIC_FORM_NAME = "public-job-form"

PUBLIC_FORM_PARAMETERS = [
    ParameterDefinition(name="resolution", type="integer", description="Grid resolution"),
    ParameterDefinition(name="duration", type="float", description="Simulation duration (seconds)"),
    ParameterDefinition(name="email", type="text", description="Notification email"),
]
