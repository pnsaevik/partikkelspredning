"""Local development entry point.

Run with:

    uvicorn partikkelspredning.main:app --reload

`api/function_app.py` hosts this exact same `app` object inside Azure
Functions via ASGI - see its module docstring.
"""
from __future__ import annotations

from partikkelspredning.api.app import create_app

app = create_app()
