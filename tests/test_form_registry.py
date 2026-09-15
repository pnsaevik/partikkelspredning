from __future__ import annotations

import json

import pytest

from partikkelspredning.domain.forms import Form
from partikkelspredning.services.form_registry import load_forms


def test_load_forms_loads_the_packaged_definitions_file():
    forms = load_forms()

    assert len(forms) >= 2
    assert all(isinstance(form, Form) for form in forms)
    ids = [form.id for form in forms]
    assert len(ids) == len(set(ids)), "form ids must be unique"
    assert "standard_resolution" in ids


def test_load_forms_parses_parameters_for_each_form():
    forms = load_forms()
    standard = next(form for form in forms if form.id == "standard_resolution")

    assert standard.name
    assert standard.description
    names = [p.name for p in standard.parameters]
    assert "resolution" in names
    assert "duration" in names


def test_load_forms_reads_a_custom_path(tmp_path):
    definitions = {
        "forms": [
            {
                "id": "custom",
                "name": "Custom form",
                "description": "A custom test form",
                "parameters": [
                    {"name": "x", "type": "integer", "description": "x value"},
                ],
            }
        ]
    }
    path = tmp_path / "definitions.json"
    path.write_text(json.dumps(definitions))

    forms = load_forms(path)

    assert len(forms) == 1
    assert forms[0].id == "custom"
    assert forms[0].parameters[0].name == "x"


def test_load_forms_rejects_duplicate_ids(tmp_path):
    definitions = {
        "forms": [
            {"id": "dup", "name": "A", "description": "", "parameters": []},
            {"id": "dup", "name": "B", "description": "", "parameters": []},
        ]
    }
    path = tmp_path / "definitions.json"
    path.write_text(json.dumps(definitions))

    with pytest.raises(ValueError, match="duplicate"):
        load_forms(path)


def test_load_forms_rejects_malformed_json(tmp_path):
    path = tmp_path / "definitions.json"
    path.write_text("not json")

    with pytest.raises(ValueError, match="JSON"):
        load_forms(path)


def test_load_forms_rejects_missing_required_field(tmp_path):
    definitions = {"forms": [{"id": "missing_name", "description": "", "parameters": []}]}
    path = tmp_path / "definitions.json"
    path.write_text(json.dumps(definitions))

    with pytest.raises(ValueError):
        load_forms(path)
