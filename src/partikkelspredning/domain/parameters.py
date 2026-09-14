"""Simulation parameter definitions and validation.

A `ParameterDefinition` describes one input a simulation expects (name,
type, human-readable description). A list of these is the single source of
truth shared by:

* the backend (`validate_parameters`, called from job submission), and
* the static form generator (`partikkelspredning.services.form_service`),
  which renders one HTML input per definition.

Keeping both driven by the same model is what avoids duplicating validation
rules between frontend and backend. The frontend's own validation (baked
into the generated HTML) is only ever a convenience - `validate_parameters`
below is the sole authority, and is always re-run server-side regardless of
what the client already checked.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from partikkelspredning.domain.errors import ParameterValidationError


class ParameterType(str, Enum):
    """The only parameter types the system understands."""

    INTEGER = "integer"
    FLOAT = "float"
    TEXT = "text"


class ParameterDefinition(BaseModel):
    """Describes one simulation input parameter.

    Reused as-is by job submission validation, the `/form` HTML generator,
    and (per the project brief) potentially future documentation/API
    generation - there is deliberately no separate "frontend" or "API"
    copy of this model.
    """

    name: str = Field(..., min_length=1)
    type: ParameterType
    description: str = ""


_INVALID = object()


def validate_parameters(
    definitions: List[ParameterDefinition],
    values: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate and coerce submitted values against their definitions.

    Returns a new dict containing exactly the defined parameters, coerced to
    their declared Python type (e.g. `"3"` -> `3` for an integer parameter).
    Raises `ParameterValidationError` listing every problem found - missing
    parameters, unknown parameters, and values of the wrong type - instead
    of stopping at the first one.
    """
    errors: List[str] = []
    result: Dict[str, Any] = {}
    defined_names = {definition.name for definition in definitions}

    for definition in definitions:
        if definition.name not in values:
            errors.append(f"Missing required parameter '{definition.name}'")
            continue
        coerced = _coerce(definition, values[definition.name], errors)
        if coerced is not _INVALID:
            result[definition.name] = coerced

    for name in values:
        if name not in defined_names:
            errors.append(f"Unknown parameter '{name}'")

    if errors:
        raise ParameterValidationError(errors)
    return result


def _coerce(definition: ParameterDefinition, raw_value: Any, errors: List[str]) -> Any:
    # bool is a subclass of int in Python; reject it explicitly for numeric
    # parameters so `True`/`False` aren't silently accepted as 1/0.
    if isinstance(raw_value, bool) and definition.type in (ParameterType.INTEGER, ParameterType.FLOAT):
        errors.append(f"Parameter '{definition.name}' must be a number, not a boolean")
        return _INVALID

    if definition.type == ParameterType.INTEGER:
        if isinstance(raw_value, int):
            return raw_value
        if isinstance(raw_value, str):
            try:
                return int(raw_value)
            except ValueError:
                pass
        errors.append(f"Parameter '{definition.name}' must be an integer")
        return _INVALID

    if definition.type == ParameterType.FLOAT:
        if isinstance(raw_value, (int, float)):
            return float(raw_value)
        if isinstance(raw_value, str):
            try:
                return float(raw_value)
            except ValueError:
                pass
        errors.append(f"Parameter '{definition.name}' must be a number")
        return _INVALID

    if definition.type == ParameterType.TEXT:
        if isinstance(raw_value, str):
            return raw_value
        errors.append(f"Parameter '{definition.name}' must be text")
        return _INVALID

    raise AssertionError(f"Unhandled parameter type: {definition.type}")  # pragma: no cover
