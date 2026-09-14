from __future__ import annotations

from partikkelspredning.domain.parameters import ParameterDefinition
from partikkelspredning.services.form_service import generate_form_html

PARAMETERS = [
    ParameterDefinition(name="resolution", type="integer", description="Horizontal grid resolution"),
    ParameterDefinition(name="duration", type="float", description="Simulation duration in days"),
    ParameterDefinition(name="experiment", type="text", description="Name of the experiment"),
]


def test_generated_form_contains_one_input_per_parameter():
    html = generate_form_html(PARAMETERS, api_base_url="http://localhost:8000")
    assert 'name="resolution"' in html
    assert 'name="duration"' in html
    assert 'name="experiment"' in html


def test_generated_form_uses_appropriate_input_types():
    html = generate_form_html(PARAMETERS, api_base_url="http://localhost:8000")
    assert 'id="resolution" name="resolution" type="number"' in html
    assert 'id="duration" name="duration" type="number" step="any"' in html
    assert 'id="experiment" name="experiment" type="text"' in html


def test_generated_form_includes_descriptions_and_email_field():
    html = generate_form_html(PARAMETERS, api_base_url="http://localhost:8000")
    assert "Horizontal grid resolution" in html
    assert 'name="user_email" type="email"' in html


def test_generated_form_embeds_the_configured_api_base_url():
    html = generate_form_html(PARAMETERS, api_base_url="https://example.com/api")
    assert '"https://example.com/api"' in html
    assert "/jobs" in html


def test_generated_form_escapes_html_in_descriptions():
    tricky = [ParameterDefinition(name="x", type="text", description="<script>alert(1)</script>")]
    html = generate_form_html(tricky, api_base_url="http://localhost:8000")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
