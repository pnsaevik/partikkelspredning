"""Azure Functions adapter.

This module is the ONLY place in the project that imports `azure.functions`.
It wires Azure's decorator-based (v2) programming model to the
platform-agnostic handlers in `partikkelspredning.handlers`, translating
Azure's HttpRequest/HttpResponse types to and from plain Python.

The actual application logic lives in `partikkelspredning.handlers` and has
no dependency on Azure. Swapping to another platform (Google Cloud
Functions, AWS Lambda, a FastAPI + container app, ...) means writing a new
adapter module like this one - the logic itself never needs to change.

New endpoints are added by: writing the logic as a plain function in
`partikkelspredning.handlers`, then decorating a thin wrapper here with
`@app.route(...)` that calls it.
"""
import json

import azure.functions as func

from partikkelspredning import handlers

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="hello", methods=["GET"])
def hello(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/hello -> {"message": "Hello, world!"}"""
    result = handlers.hello()
    return func.HttpResponse(
        json.dumps(result),
        mimetype="application/json",
        status_code=200,
    )
