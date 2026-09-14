# API stub - Azure Functions adapter

This folder is a thin Azure Functions **adapter**: it is the only place
(besides `../src/partikkelspredning/adapters/azure/`) that imports Azure
SDKs. `function_app.py` hosts the platform-agnostic FastAPI application
from [`partikkelspredning`](../src/partikkelspredning) directly inside
Azure Functions via ASGI (`func.AsgiFunctionApp`) - it is the *same* app
`uvicorn partikkelspredning.main:app` runs locally, not a reimplementation.
See [the root README](../README.md) for the full architecture.

## Run locally

Requires the [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
and a Python version supported by the Azure Functions Python worker (3.9-3.12).

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
func start
```

Then visit `http://localhost:7071/api/docs` for the interactive OpenAPI
docs (same endpoints as running `uvicorn` directly - see the root README).

`local.settings.json` defaults `PARTIKKEL_STORAGE_MODE` to `local`, so
`func start` works with no Azure Storage account for the *application's
own* data - CSV files are written under `PARTIKKEL_LOCAL_DATA_DIR`. Note
that `AzureWebJobsStorage` (required by the Functions *host* itself, not by
our code) is left blank here; a real deployment needs it set, either to a
real storage account connection string or `UseDevelopmentStorage=true`
against the [Azurite emulator](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

## Deploy to Azure

```bash
# one-time setup, if the resources don't exist yet
az login
az group create --name <resource-group> --location <region>
az storage account create --name <storage-account> --resource-group <resource-group> --sku Standard_LRS
az functionapp create --resource-group <resource-group> --consumption-plan-location <region> \
  --runtime python --runtime-version <3.x> --functions-version 4 \
  --name <function-app-name> --storage-account <storage-account> --os-type Linux

# app settings for the *application's* own storage mode (separate from
# AzureWebJobsStorage, which the Functions host manages itself)
az functionapp config appsettings set --name <function-app-name> --resource-group <resource-group> \
  --settings PARTIKKEL_STORAGE_MODE=azure AZURE_STORAGE_CONNECTION_STRING="<connection-string>" \
             PARTIKKEL_API_BASE_URL="https://<function-app-name>.azurewebsites.net/api"

# deploy this folder's code
cd api
func azure functionapp publish <function-app-name>
```

`local.settings.json` is for local development only - it is git-ignored and
never deployed (see `.funcignore`); app settings for the deployed function
are configured on the Azure resource itself, as above.

**Known caveat:** `requirements.txt` installs `partikkelspredning` in
editable mode from `..` (the repo root), which works for local `func start`
but not for `func azure functionapp publish`, since only this `api/` folder
is uploaded for the remote build and `..` won't exist there. Until this is
solved (e.g. by building a wheel of `partikkelspredning` into
`api/.python_packages` before publishing, or publishing it to a package
index), treat `func azure functionapp publish` as untested for this repo
layout.
