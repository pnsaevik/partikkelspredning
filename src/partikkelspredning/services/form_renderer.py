"""Static HTML form generation and the forms-registry pre-rendering pipeline.

`generate_form_html` turns a list of `ParameterDefinition`s into a single,
dependency-free HTML page: a plain `<form>` with one labelled input per
parameter (using the appropriate `type=` attribute and basic client-side
validation), a submit button, and a small inline `<script>` that POSTs the
values as JSON to the configured API base URL and shows the returned job ID
or an error message.

This module is presentation only. `POST /jobs` itself accepts parameters as
an arbitrary JSON object with no predefined schema (see
`partikkelspredning.domain.parameters`) - it never validates against the
definitions used to generate a given form. Whether submitted values are
actually usable is for the compute server that eventually claims the job to
decide, not this form. The generated page's client-side type checks are
purely a UX convenience for whichever form this happens to be. Nothing here
is HTML-specific business logic, so it stays out of the domain layer.

`render_forms`/`render_index_html`/`prerender_and_store` build on
`generate_form_html` for the forms registry (see FEATURE_PLAN.md's
"multiple_forms"): every `Form` loaded by `services.form_registry` is
rendered and uploaded via a `FormStore` at startup, and an index page
linking to each is rendered alongside it. The pre-existing, unrelated
single "public form" feature (`services.public_form_service`) also reuses
`generate_form_html` directly.
"""
from __future__ import annotations

import json
from html import escape
from typing import Dict, List

from partikkelspredning.domain.forms import Form
from partikkelspredning.domain.parameters import ParameterDefinition, ParameterType
from partikkelspredning.ports.form_store import FormStore

_INPUT_TYPE = {
    ParameterType.INTEGER: "number",
    ParameterType.FLOAT: "number",
    ParameterType.TEXT: "text",
}


def _field_html(definition: ParameterDefinition) -> str:
    input_type = _INPUT_TYPE[definition.type]
    step_attr = ' step="any"' if definition.type == ParameterType.FLOAT else ""
    name = escape(definition.name, quote=True)
    description = escape(definition.description)
    return f"""
      <div class="field">
        <label for="{name}">{escape(definition.name)}</label>
        <input id="{name}" name="{name}" type="{input_type}"{step_attr} required>
        <p class="description">{description}</p>
      </div>"""


def generate_form_html(
    parameters: List[ParameterDefinition],
    *,
    api_base_url: str,
    title: str = "Submit simulation job",
) -> str:
    """Render a complete, standalone HTML page for submitting a job.

    The page POSTs to `f"{api_base_url}/jobs"`; `api_base_url` is baked in
    at generation time, so the saved HTML file works as-is as long as the
    backend it points to is reachable (see the root README).
    """
    fields_html = "\n".join(_field_html(definition) for definition in parameters)
    numeric_field_names_json = json.dumps(
        [d.name for d in parameters if d.type in (ParameterType.INTEGER, ParameterType.FLOAT)]
    )
    api_base_url_json = json.dumps(api_base_url)
    title_html = escape(title)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title_html}</title>
<style>
  body {{ font-family: sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; }}
  .field {{ margin-bottom: 1.25rem; }}
  label {{ display: block; font-weight: bold; margin-bottom: 0.25rem; }}
  input {{ width: 100%; padding: 0.4rem; box-sizing: border-box; }}
  .description {{ margin: 0.25rem 0 0; color: #555; font-size: 0.9em; }}
  button {{ padding: 0.5rem 1.25rem; }}
  #status {{ margin-top: 1rem; padding: 0.75rem; border-radius: 4px; display: none; }}
  #status.success {{ display: block; background: #e6f4ea; color: #1e4620; }}
  #status.error {{ display: block; background: #fdecea; color: #611a15; }}
</style>
</head>
<body>
<h1>{title_html}</h1>
<form id="job-form" novalidate>
{fields_html}
  <div class="field">
    <label for="user_email">Email</label>
    <input id="user_email" name="user_email" type="email" required>
    <p class="description">You will be notified at this address when the job completes.</p>
  </div>
  <button type="submit">Submit</button>
</form>
<div id="status"></div>
<script>
(function () {{
  var API_BASE_URL = {api_base_url_json};
  var NUMERIC_FIELDS = {numeric_field_names_json};
  var form = document.getElementById("job-form");
  var status = document.getElementById("status");

  function showStatus(className, message) {{
    status.className = className;
    status.textContent = message;
  }}

  form.addEventListener("submit", function (event) {{
    event.preventDefault();
    showStatus("", "");

    var formData = new FormData(form);
    var userEmail = formData.get("user_email");
    var parameters = {{}};
    var invalid = [];

    formData.forEach(function (value, key) {{
      if (key === "user_email") return;
      if (NUMERIC_FIELDS.indexOf(key) !== -1) {{
        var n = Number(value);
        if (value === "" || isNaN(n)) {{
          invalid.push(key);
        }} else {{
          parameters[key] = n;
        }}
      }} else {{
        parameters[key] = value;
      }}
    }});

    if (invalid.length > 0) {{
      showStatus("error", "Please enter a valid number for: " + invalid.join(", "));
      return;
    }}

    fetch(API_BASE_URL + "/jobs", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ user_email: userEmail, parameters: parameters }})
    }})
      .then(function (response) {{
        return response.json().then(function (body) {{
          return {{ ok: response.ok, body: body }};
        }});
      }})
      .then(function (result) {{
        if (result.ok) {{
          showStatus("success", "Job submitted. Job ID: " + result.body.job_id + " (status: " + result.body.status + ")");
          form.reset();
        }} else {{
          var detail = result.body && result.body.detail ? result.body.detail : "Submission failed.";
          showStatus("error", "Error: " + JSON.stringify(detail));
        }}
      }})
      .catch(function (err) {{
        showStatus("error", "Network error: " + err.message);
      }});
  }});
}})();
</script>
</body>
</html>
"""


def render_forms(forms: List[Form], *, api_base_url: str) -> Dict[str, str]:
    """Render one standalone HTML page per form; returns `{form.id: html}`."""
    return {
        form.id: generate_form_html(form.parameters, api_base_url=api_base_url, title=form.name)
        for form in forms
    }


def render_index_html(forms: List[Form], form_urls: Dict[str, str]) -> str:
    """Render a static landing page linking to each form's pre-rendered URL."""
    items_html = "\n".join(
        f"""    <li>
      <a href="{escape(form_urls[form.id], quote=True)}">{escape(form.name)}</a>
      <p class="description">{escape(form.description)}</p>
    </li>"""
        for form in forms
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Available simulation forms</title>
<style>
  body {{ font-family: sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; }}
  li {{ margin-bottom: 1.25rem; }}
  .description {{ margin: 0.25rem 0 0; color: #555; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>Available simulation forms</h1>
<ul>
{items_html}
</ul>
</body>
</html>
"""


def prerender_and_store(forms: List[Form], form_store: FormStore, *, api_base_url: str) -> Dict[str, str]:
    """Render every form and upload it via `form_store`; returns `{form.id: url}`.

    Called once at startup (see `api.app.create_app`'s startup handler and
    `api.function_app`'s lazily cached singletons) so forms are served as
    pre-rendered static assets rather than generated per-request.
    """
    rendered = render_forms(forms, api_base_url=api_base_url)
    return {form.id: form_store.upload_form_html(form.id, rendered[form.id]) for form in forms}
