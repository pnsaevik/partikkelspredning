from __future__ import annotations

import pytest

from partikkelspredning.domain.errors import ParameterValidationError
from partikkelspredning.domain.parameters import ParameterDefinition, validate_parameters

DEFINITIONS = [
    ParameterDefinition(name="resolution", type="integer", description="Grid resolution"),
    ParameterDefinition(name="duration", type="float", description="Duration in days"),
    ParameterDefinition(name="experiment", type="text", description="Experiment name"),
]


def test_valid_parameters_pass_through_and_coerce_types():
    result = validate_parameters(
        DEFINITIONS, {"resolution": "100", "duration": "1.5", "experiment": "demo"}
    )
    assert result == {"resolution": 100, "duration": 1.5, "experiment": "demo"}
    assert isinstance(result["resolution"], int)
    assert isinstance(result["duration"], float)


def test_integer_accepts_plain_int_and_float_accepts_int():
    result = validate_parameters(DEFINITIONS, {"resolution": 50, "duration": 2, "experiment": "x"})
    assert result == {"resolution": 50, "duration": 2.0, "experiment": "x"}


def test_missing_parameter_is_reported():
    with pytest.raises(ParameterValidationError) as exc_info:
        validate_parameters(DEFINITIONS, {"resolution": 1, "duration": 1.0})
    assert any("experiment" in message for message in exc_info.value.errors)


def test_unknown_parameter_is_reported():
    with pytest.raises(ParameterValidationError) as exc_info:
        validate_parameters(
            DEFINITIONS,
            {"resolution": 1, "duration": 1.0, "experiment": "x", "bogus": "y"},
        )
    assert any("bogus" in message for message in exc_info.value.errors)


def test_wrong_type_is_reported():
    with pytest.raises(ParameterValidationError) as exc_info:
        validate_parameters(DEFINITIONS, {"resolution": "not-a-number", "duration": 1.0, "experiment": "x"})
    assert any("resolution" in message for message in exc_info.value.errors)


def test_boolean_is_rejected_for_numeric_parameters():
    with pytest.raises(ParameterValidationError) as exc_info:
        validate_parameters(DEFINITIONS, {"resolution": True, "duration": 1.0, "experiment": "x"})
    assert any("resolution" in message for message in exc_info.value.errors)


def test_all_problems_are_reported_at_once():
    with pytest.raises(ParameterValidationError) as exc_info:
        validate_parameters(DEFINITIONS, {"resolution": "bad", "bogus": "y"})
    # missing 'duration', missing 'experiment', bad 'resolution', unknown 'bogus'
    assert len(exc_info.value.errors) == 4
