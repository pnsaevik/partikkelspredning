from __future__ import annotations

from fakes import RecordingFormStore

from partikkelspredning.domain.forms import Form
from partikkelspredning.domain.parameters import ParameterDefinition
from partikkelspredning.services.form_renderer import (
    generate_form_html,
    prerender_and_store,
    render_forms,
    render_index_html,
)

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


def _forms():
    return [
        Form(id="a", name="Form A", description="First form", parameters=PARAMETERS[:1]),
        Form(id="b", name="Form B", description="Second form", parameters=PARAMETERS[1:]),
    ]


def test_render_forms_renders_one_html_page_per_form():
    rendered = render_forms(_forms(), api_base_url="http://localhost:8000")
    assert set(rendered.keys()) == {"a", "b"}
    assert 'name="resolution"' in rendered["a"]
    assert 'name="duration"' in rendered["b"]


def test_render_index_html_links_to_each_form():
    forms = _forms()
    form_urls = {"a": "https://example.com/forms/a.html", "b": "https://example.com/forms/b.html"}

    html = render_index_html(forms, form_urls)

    assert "Form A" in html
    assert "First form" in html
    assert 'href="https://example.com/forms/a.html"' in html
    assert 'href="https://example.com/forms/b.html"' in html


def test_render_index_html_escapes_form_metadata():
    forms = [Form(id="x", name="<script>alert(1)</script>", description="", parameters=[])]
    html = render_index_html(forms, {"x": "https://example.com/forms/x.html"})
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_prerender_and_store_uploads_each_form_and_returns_urls():
    form_store = RecordingFormStore()

    urls = prerender_and_store(_forms(), form_store, api_base_url="http://localhost:8000")

    assert urls == {"a": "fake://forms/a.html", "b": "fake://forms/b.html"}
    assert 'name="resolution"' in form_store.uploaded["a"]
    assert 'name="duration"' in form_store.uploaded["b"]
