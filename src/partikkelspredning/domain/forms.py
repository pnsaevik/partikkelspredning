"""One named, pre-configured form in the forms registry.

A `Form` pairs an id (used as its storage key and URL slug) and
human-readable name/description with the `ParameterDefinition` list that
describes its fields - the same shape `domain.public_forms` and
`services.form_renderer.generate_form_html` already use for a single
hardcoded form. `services.form_registry.load_forms` is what turns the
packaged `forms/definitions.json` into a list of these.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from partikkelspredning.domain.parameters import ParameterDefinition


class Form(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = ""
    parameters: List[ParameterDefinition] = Field(default_factory=list)
