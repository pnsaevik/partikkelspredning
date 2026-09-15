"""Loads the forms registry (`forms/definitions.json`) into `Form` objects.

The packaged JSON file is the source of truth for which forms exist (see
FEATURE_PLAN.md's "multiple_forms": forms are source-code-only, no admin
endpoints yet). `load_forms` is called once at startup (see
`api.app.create_app`'s startup handler and `api.function_app`'s lazily
cached singletons) so a malformed file fails fast before the app starts
serving requests, rather than surfacing as a runtime error later.
"""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import List, Optional

from pydantic import ValidationError

from partikkelspredning.domain.forms import Form

_PACKAGE = "partikkelspredning.forms"
_FILENAME = "definitions.json"


def load_forms(path: Optional[Path] = None) -> List[Form]:
    """Parse the forms registry into a list of `Form`.

    Loads the packaged `forms/definitions.json` (via `importlib.resources`,
    so it works from both an editable install and a built wheel) unless an
    explicit `path` is given. Raises `ValueError` for malformed JSON, a
    missing/invalid `Form` field, or duplicate form ids - the registry is
    meant to fail fast rather than start the app with an inconsistent set
    of forms.
    """
    if path is None:
        raw_text = resources.files(_PACKAGE).joinpath(_FILENAME).read_text(encoding="utf-8")
    else:
        raw_text = Path(path).read_text(encoding="utf-8")

    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Forms definitions file is not valid JSON: {exc}") from exc

    try:
        raw_forms = raw["forms"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Forms definitions file must have a top-level 'forms' list") from exc

    try:
        forms = [Form.model_validate(entry) for entry in raw_forms]
    except ValidationError as exc:
        raise ValueError(f"Invalid form definition: {exc}") from exc

    ids = [form.id for form in forms]
    duplicates = {form_id for form_id in ids if ids.count(form_id) > 1}
    if duplicates:
        raise ValueError(f"Forms definitions file has duplicate form ids: {sorted(duplicates)}")

    return forms
