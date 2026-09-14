"""TEMPORARY diagnostic endpoint - Flex Consumption deployment smoke test.

The real FastAPI/ASGI app (see `function_app_fastapi.py.disabled`, moved
aside rather than deleted) is not currently coming up healthy on
`partikkelspredning-api`'s Flex Consumption plan - the deploy step itself
succeeds, but the deployed app never returns 200 (see CHANGELOG.md's
[0.1.4] entry). This file replaces it with the smallest possible Python
Azure Function - no FastAPI, no ASGI, no `partikkelspredning` import, no
Azure SDKs - to isolate whether *anything* can run on this Function App at
all before debugging the full app further.

This is deliberately throwaway: once the underlying issue is understood,
revert this commit to restore `function_app.py` from
`function_app_fastapi.py.disabled` and go back to hosting the real app.
"""
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="hello", methods=["GET"])
def hello(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("Hello, world!")
