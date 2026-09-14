"""FastAPI adapter: translates HTTP to/from the application services.

This is the primary local-development interface (see
`partikkelspredning.main`) and is also what `api/function_app.py` hosts
inside Azure Functions via ASGI - the same app, unchanged, in both cases.
"""
