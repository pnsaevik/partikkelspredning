from __future__ import annotations

from fakes import RecordingFormStore

from partikkelspredning.domain.public_forms import PUBLIC_FORM_NAME, PUBLIC_FORM_PARAMETERS
from partikkelspredning.services.public_form_service import deploy_public_form


def test_deploy_public_form_uploads_html_for_the_fixed_parameter_set():
    form_store = RecordingFormStore()

    deploy_public_form(form_store, api_base_url="https://example.com/api")

    html = form_store.uploaded[PUBLIC_FORM_NAME]
    assert 'name="resolution"' in html
    assert 'name="duration"' in html
    assert 'name="email"' in html
    assert '"https://example.com/api"' in html


def test_deploy_public_form_returns_the_form_stores_public_url():
    form_store = RecordingFormStore()

    url = deploy_public_form(form_store, api_base_url="https://example.com/api")

    assert url == f"fake://forms/{PUBLIC_FORM_NAME}.html"


def test_public_form_parameters_match_the_feature_plans_fixed_set():
    names_and_types = [(p.name, p.type.value) for p in PUBLIC_FORM_PARAMETERS]
    assert names_and_types == [
        ("resolution", "integer"),
        ("duration", "float"),
        ("email", "text"),
    ]
