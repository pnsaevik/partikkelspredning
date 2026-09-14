# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The job-submission/tracking backend for a future particle-dispersion simulation
system. `POST /jobs` accepts simulation parameters as an arbitrary JSON
object — there is no predefined parameter schema this backend validates
against — and queues the job. A future compute server (not implemented in
this repo) will claim queued jobs, decide whether a given job's parameters
are actually runnable, run the simulation, and report completion/failure
back. `POST /form` is a separate, unrelated convenience: it generates a
static HTML form for one specific parameter set (e.g.
resolution/duration/experiment) — not deployed by this repo, and its shape
has no bearing on what `POST /jobs` accepts. First deployment target is
Azure, but business logic never imports an Azure SDK.

## Commands

```bash
# install (editable, with dev + local extras)
pip install -e ".[dev,local]"

# run the full test suite
pytest

# run a single test file / test
pytest tests/test_job_service.py
pytest tests/test_job_service.py::test_name

# run the app locally
uvicorn partikkelspredning.main:app --reload
# -> interactive docs at http://localhost:8000/docs
```

Optional Azure integration tests (`tests/azure_integration/`, marked
`azure_integration`) are excluded by default via `addopts` in
`pyproject.toml`. Run them explicitly against a real or
[Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite)-emulated
storage account:

```bash
pip install -e ".[azure]"
AZURE_STORAGE_CONNECTION_STRING="..." pytest -m azure_integration
```

## Architecture: ports and adapters, strictly layered

```
api/ (FastAPI routes, schemas, DI)
  -> services/ (JobService, form_service)
       -> domain/ (SimulationJob, JobStatus, parameters)
       -> ports/  (Protocols: JobRepository, JobQueue, ResultStore, NotificationService)
                       implemented by:
                       adapters/local/ (CSV files, disk, console logging - no cloud creds)
                       adapters/azure/ (Table Storage, Storage Queue, Blob Storage)
```

Import rules, enforced by convention (not tooling) — do not violate them:

| Layer | Path | May import |
|---|---|---|
| Domain | `src/partikkelspredning/domain/` | pydantic only |
| Services | `src/partikkelspredning/services/` | domain, ports |
| Ports | `src/partikkelspredning/ports/` | domain (typing only) |
| Local adapters | `src/partikkelspredning/adapters/local/` | domain, ports, pandas |
| Azure adapters | `src/partikkelspredning/adapters/azure/` | domain, ports, `azure.*` |
| API | `src/partikkelspredning/api/` | everything above, FastAPI |
| Azure Functions | `api/function_app.py` | `partikkelspredning`, `azure.functions` |

`domain/`, `services/`, and `ports/` must never import `azure`,
`azure-functions`, `pandas`, or `fastapi`. `partikkelspredning.composition`
is the sole composition root: it picks concrete adapters based on
`PARTIKKEL_STORAGE_MODE` (`local`/`azure`) and wires them into a
`JobService` — nothing above it should know which adapters were chosen.

Both hosting modes call into the *same* `services`/`domain`/`ports` layer,
never a reimplementation of the business logic — only the HTTP transport
differs:

```
local:  browser -> uvicorn -> FastAPI app (partikkelspredning.main:app)
Azure:  browser -> Azure Functions -> HTTP-triggered functions (api/function_app.py),
                                       each a thin wrapper around the same JobService
```

`api/` at the repo root is a thin Azure Functions adapter folder (separate
from `src/partikkelspredning/api/`, the FastAPI route layer) — see
`api/README.md` for local `func start` usage and deployment. Only this
folder is uploaded for `func azure functionapp publish`'s remote build (it
zips whatever directory contains `host.json`), so `api/requirements.txt`
doesn't pin `partikkelspredning` directly — an editable `-e ..` install
wouldn't survive that upload boundary. Instead, a `partikkelspredning @
git+https://github.com/<owner>/<repo>.git@<commit>` line, pinned to the
exact commit being deployed, is appended to that checked-out copy of the
file right before deployment (`action_deploy.yml` for CI; see
`api/README.md`'s "How packaging works" for the manual equivalent) —
never committed, so `pip install -e ..` (see the same README section) is
what local development uses instead.

## Job lifecycle

```
queued -> processing -> completed
                      -> failed
```

`queued`/`processing` are the only non-terminal states. The full transition
table lives in `partikkelspredning.domain.jobs.ALLOWED_TRANSITIONS` and is
enforced by `SimulationJob.transition_status` — nothing else may assign to
`job.status` directly. There is no lease/timeout/retry mechanism yet for a
worker that claims a job and disappears; `SimulationJob` already carries
`worker_id`/`claimed_at` so one can be added later without a data migration.

## Parameter definitions

`POST /jobs` has **no predefined parameter schema** — `parameters` is
accepted as an arbitrary JSON object and stored as-is; whether a job is
actually runnable is for the (not-yet-implemented) compute server to decide
once it claims it, not this API. `partikkelspredning.domain.parameters
.ParameterDefinition` (`name`, `type`, `description`; only `integer`,
`float`, `text` supported) exists solely to describe the fields of one
generated form — `POST /form` takes a list of these directly in its request
body and renders a standalone HTML page for that specific parameter set. It
is a static-site-generator convenience, not deployed by this repo, and
unrelated to what `POST /jobs` will accept.

## Configuration

All configuration is via environment variables
(`src/partikkelspredning/config.py`) — no resource names or credentials are
hard-coded. Key ones: `PARTIKKEL_STORAGE_MODE` (`local`/`azure`, default
`local`), `PARTIKKEL_LOCAL_DATA_DIR` (default `./data`),
`AZURE_STORAGE_CONNECTION_STRING` (required in azure mode). Full table in
the root README.

`local` mode storage: `adapters/local` keeps job metadata in
`PARTIKKEL_LOCAL_DATA_DIR/jobs.csv` (pandas), the queue as one job id per
line in `queue.txt`, results under `results/`, and logs notifications to the
console. Both CSV files are guarded by an `fcntl`-based exclusive lock
around each read-modify-write — intentionally simple, not a production
database (that's what `adapters/azure/` is for).

## Security posture (prototype, deliberately minimal)

* Request structure (e.g. `user_email` format) is validated server-side
  regardless of client-side checks. Job `parameters` content is
  deliberately *not* validated against any schema — see "Parameter
  definitions" above.
* Job IDs are server-generated (`uuid4`); a client-supplied `job_id` is only
  ever used to look up a job, never trusted for authorization.
* `claim`/`complete`/`fail` (the endpoints the future compute server calls)
  have **no authentication yet** — each depends on
  `partikkelspredning.api.security.require_worker_auth`, currently a no-op
  by design, so real auth can be added in one place later.
* `JobService` separately checks that only the worker that claimed a job can
  complete/fail it (`JobOwnershipError`) — a correctness safeguard, not a
  substitute for real authentication.

## Not implemented in this repo

The compute server / ocean model itself, real email delivery, sophisticated
authentication, a lease/retry mechanism for stale claims, and anything
Kubernetes-related. See the root README's "Scope of this iteration" section.
