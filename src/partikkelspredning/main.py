"""Local development entry point.

Run with:

    uvicorn partikkelspredning.main:app --reload

A deployed Azure Function App does not host this `app` object - it runs its
own HTTP-triggered functions instead (`api/function_app.py`), each a thin
wrapper around the same `JobService`/`services` layer this app's routes
call. See that module's docstring for why.
"""
from __future__ import annotations

from partikkelspredning.api.app import create_app

app = create_app()
