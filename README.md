# Partikkelspredning

## Architecture

The project keeps a hard separation between application logic and hosting
platform:

- **`src/partikkelspredning/`** — the platform-agnostic core. Plain Python
  functions that take and return plain values, with no dependency on any
  cloud SDK. This is what actually implements the application's behavior,
  and it can be imported and unit-tested on its own.
- **`api/`** — a thin Azure Functions *adapter*. It is the only place that
  imports `azure.functions`; its job is only to translate Azure's
  request/response types to and from plain Python and call into
  `partikkelspredning`.

The point of this split is that the adapter is the only part that's
Azure-specific. Moving to a different platform (Google Cloud Functions, AWS
Lambda, a FastAPI app in a container, ...) means writing a new thin adapter
next to `api/` that calls the same `partikkelspredning` functions — the
core logic itself never has to change.

See [`api/README.md`](api/README.md) for how to run and deploy the Azure
Functions adapter.

## Tests

The `tests/` directory covers `src/partikkelspredning` only — plain unit
tests with no Azure Functions host and no `azure.functions` involved, since
the logic under test doesn't depend on either.

```bash
pip install -e ".[dev]"
pytest
```
