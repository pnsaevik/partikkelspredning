"""Azure Functions adapter.

This module (together with everything under
`partikkelspredning.adapters.azure`) is the only place that imports Azure
SDKs. It hosts the exact same FastAPI application used for local
development directly inside Azure Functions, using the standard ASGI
hosting support (`func.AsgiFunctionApp`) instead of re-declaring every route
as a separate Azure Function - so the two hosting modes can never drift
apart:

    local:  browser -> uvicorn -> FastAPI app (partikkelspredning.main:app)
    Azure:  browser -> Azure Functions -> the *same* FastAPI app, via ASGI

Which storage adapters that FastAPI app itself uses (local CSV files vs.
Azure Table/Queue/Blob Storage) is controlled independently by the
`PARTIKKEL_STORAGE_MODE` app setting/environment variable - see the root
README and `partikkelspredning.config`. A deployed Function App will
normally set `PARTIKKEL_STORAGE_MODE=azure` plus
`AZURE_STORAGE_CONNECTION_STRING`.

New endpoints are added in `partikkelspredning.api` (a router + a line in
`partikkelspredning.api.app.create_app`), never here - this file never needs
to change when the API grows.
"""
import azure.functions as func

from partikkelspredning.main import app as fastapi_app

app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
