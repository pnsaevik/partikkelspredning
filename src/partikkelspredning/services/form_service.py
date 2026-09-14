"""Static HTML form generation.

Turns a list of `ParameterDefinition`s into a single, dependency-free HTML
page: a plain `<form>` with one labelled input per parameter (using the
appropriate `type=` attribute and basic client-side validation), a submit
button, and a small inline `<script>` that POSTs the values as JSON to the
configured API base URL and shows the returned job ID or an error message.

This module is presentation only - it does not decide whether the values
are *actually* valid; that's `partikkelspredning.domain.parameters
.validate_parameters`'s job, which the generated page's own client-side
checks intentionally mirror only loosely, as a convenience, never as the
source of truth. Nothing here is HTML-specific business logic, so it stays
out of the domain layer.
"""
from __future__ import annotations

import json
from html import escape
from typing import List

from partikkelspredning.domain.parameters import ParameterDefinition, ParameterType

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
