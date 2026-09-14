"""Platform-agnostic request handlers.

Functions in this module contain the actual application logic and know
nothing about any specific hosting platform (Azure Functions, Google Cloud
Functions, AWS Lambda, a FastAPI app, ...). They take and return plain
Python values only.

Each platform gets its own thin "adapter" (for example `api/function_app.py`
for Azure Functions) whose only job is to translate that platform's
request/response types to and from plain Python and call into these
functions. To move to a different platform, write a new adapter against
this module - the logic here never has to change.
"""
from __future__ import annotations


def hello() -> dict:
    """Business logic behind the `hello` endpoint."""
    return {"message": "Hello, world!"}
