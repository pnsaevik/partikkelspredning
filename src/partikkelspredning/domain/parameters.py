"""Simulation parameter *description*, for the static form generators only.

A `ParameterDefinition` describes one input a simulation form should collect
(name, type, human-readable description). It exists solely so
`partikkelspredning.services.form_renderer` can render one HTML input per
definition - used by the forms registry (`domain.forms.Form`, pre-rendered
at startup and served via `GET /`/`GET /forms`) and by the pre-existing,
unrelated single public form (`domain.public_forms.PUBLIC_FORM_PARAMETERS`,
deployed via `scripts/deploy_public_form.py`).

This is deliberately *not* a schema job submission is validated against:
`POST /jobs` accepts parameters as an arbitrary JSON object (see
`partikkelspredning.api.schemas.SubmitJobRequest`) with no predefined
parameter set. Whether a given job's parameters are actually usable is for
the (not-yet-implemented) compute server to decide once it claims the job -
see the root README's "How the compute server is expected to interact with
the API".
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ParameterType(str, Enum):
    """The input types the form generators know how to render a field for."""

    INTEGER = "integer"
    FLOAT = "float"
    TEXT = "text"


class ParameterDefinition(BaseModel):
    """Describes one field of a generated form.

    Used only by the form generators (see the module docstring) - not by
    job submission.
    """

    name: str = Field(..., min_length=1)
    type: ParameterType
    description: str = ""
