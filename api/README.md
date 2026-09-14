# API stub

Minimal Azure Functions app (Python v2 programming model), ready to grow and
to be deployed as-is.

This app is a thin **adapter**: it is the only place that imports
`azure.functions`, and its only job is to translate Azure's
request/response types to and from plain Python and call into the
platform-agnostic business logic in
[`partikkelspredning.handlers`](../src/partikkelspredning/handlers.py). That
logic has no Azure dependency and no dependency on this folder at all, so it
can be tested, reused, or wrapped by a different adapter (Google Cloud
Functions, AWS Lambda, a FastAPI route, ...) without being touched. See
[the root README](../README.md#architecture) for more on this split.

## Endpoints

- `GET /api/hello` -> `{"message": "Hello, world!"}`

## Run locally

Requires the [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
and a Python version supported by the Azure Functions Python worker (3.9–3.12).

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
func start
```

Then visit `http://localhost:7071/api/hello`.

## Add a new endpoint

1. Write the actual logic as a plain function in
   `../src/partikkelspredning/handlers.py` (no `azure.functions` import
   there).
2. Add a thin wrapper to `function_app.py`, decorated with
   `@app.route(...)`, that extracts input from `func.HttpRequest`, calls the
   handler, and wraps the result in a `func.HttpResponse` — no extra files
   or config needed (that's how the v2 model works).

## Deploy to Azure

```bash
# one-time setup, if the resources don't exist yet
az login
az group create --name <resource-group> --location <region>
az storage account create --name <storage-account> --resource-group <resource-group> --sku Standard_LRS
az functionapp create --resource-group <resource-group> --consumption-plan-location <region> \
  --runtime python --runtime-version <3.x> --functions-version 4 \
  --name <function-app-name> --storage-account <storage-account> --os-type Linux

# deploy this folder's code
cd api
func azure functionapp publish <function-app-name>
```

`local.settings.json` is for local development only — it is git-ignored and
never deployed (see `.funcignore`); app settings for the deployed function
(such as `AzureWebJobsStorage`) are configured on the Azure resource itself.

**Known caveat:** `requirements.txt` installs `partikkelspredning` in
editable mode from `..` (the repo root), which works for local `func start`
but not for `func azure functionapp publish`, since only this `api/` folder
is uploaded for the remote build — `..` won't exist there. Until this is
solved (e.g. by building a wheel of `partikkelspredning` into
`api/.python_packages` before publishing, or publishing it to a package
index), treat `func azure functionapp publish` as untested for this repo
layout.
