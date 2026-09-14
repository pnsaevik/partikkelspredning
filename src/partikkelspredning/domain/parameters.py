"""Simulation parameter *description*, for the static form generator only.

A `ParameterDefinition` describes one input a simulation form should collect
(name, type, human-readable description). It exists solely so
`partikkelspredning.services.form_service` can render one HTML input per
definition for the `POST /form` convenience endpoint - a static-site
generator for a particular kind of form (e.g. resolution/duration/
experiment), not deployed anywhere by this repo.

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
    """The input types `POST /form` knows how to render a field for."""

    INTEGER = "integer"
    FLOAT = "float"
    TEXT = "text"


class ParameterDefinition(BaseModel):
    """Describes one field of a generated form.

    Used only by `POST /form` (see the module docstring) - not by job
    submission.
    """

    name: str = Field(..., min_length=1)
    type: ParameterType
    description: str = ""
