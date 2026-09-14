# Partikkelspredning - job submission backend

The job-submission/tracking backend for a future particle-dispersion
simulation system. A client submits simulation parameters as an arbitrary
JSON object - there is no predefined parameter schema this backend
validates against; it accepts and stores the job as queued. A future
compute server (**not implemented here**) will claim queued jobs and is the
one that decides whether a given job's parameters are actually runnable,
then reports completion or failure back. A convenience endpoint
(`POST /form`) can generate a static HTML form for a specific parameter set
(e.g. resolution/duration/experiment), but that form isn't deployed by this
repo and its shape has no bearing on what `POST /jobs` will accept.

The first deployment target is Azure, but the architecture deliberately
minimizes vendor lock-in: business logic never imports an Azure SDK.

## Architecture

Layered / ports-and-adapters:

```
                          ┌───────────────────────────┐
                          │   api/  (FastAPI routes)   │
                          │  schemas, routers, DI      │
                          └─────────────┬─────────────┘
                                        │ calls
                          ┌─────────────▼─────────────┐
                          │   services/  (JobService,  │
                          │   form_service)             │
                          └──────┬───────────────┬─────┘
                                 │ uses           │ uses
                     ┌───────────▼───┐      ┌─────▼───────────┐
                     │  domain/       │      │  ports/  (Protocols)│
                     │  SimulationJob,│      │  JobRepository,      │
                     │  JobStatus,    │      │  JobQueue,            │
                     │  parameters    │      │  ResultStore,          │
                     └────────────────┘      │  NotificationService   │
                                              └──────────┬─────────────┘
                                 implemented by ┌─────────┴─────────┐
                                                │                   │
                                     ┌──────────▼───────┐ ┌─────────▼─────────┐
                                     │ adapters/local/   │ │ adapters/azure/    │
                                     │ CSV files, disk,  │ │ Table Storage,      │
                                     │ console logging   │ │ Storage Queue,       │
                                     │ (no cloud creds)  │ │ Blob Storage         │
                                     └───────────────────┘ └─────────────────────┘
```

```
local:  browser -> uvicorn -> FastAPI app (partikkelspredning.main:app)
Azure:  browser -> Azure Functions -> HTTP-triggered functions
                                       (api/function_app.py)
```

The Azure Functions adapter doesn't reimplement the business logic: each
HTTP-triggered function in `api/function_app.py` is a thin wrapper that
translates a request straight into a call on the same `JobService` the
FastAPI routes use, reusing the same request/response schemas and domain
error handling - so the two hosting modes can't drift apart on anything but
HTTP transport. Unlike the FastAPI app, it has no interactive `/docs` (see
"API" below).

### Separation of concerns

| Layer | Path | May import |
|---|---|---|
| Domain | `src/partikkelspredning/domain/` | pydantic only |
| Services | `src/partikkelspredning/services/` | domain, ports |
| Ports | `src/partikkelspredning/ports/` | domain (typing only) |
| Local adapters | `src/partikkelspredning/adapters/local/` | domain, ports, pandas |
| Azure adapters | `src/partikkelspredning/adapters/azure/` | domain, ports, `azure.*` |
| API | `src/partikkelspredning/api/` | everything above, FastAPI |
| Azure Functions | `api/function_app.py` | `partikkelspredning`, `azure.functions` |

**`domain/`, `services/`, and `ports/` contain no `azure`, `azure-functions`,
`pandas`, or `fastapi` imports.** `partikkelspredning.composition` is the one
place ("composition root") that picks concrete adapters based on
configuration and wires them into a `JobService`; nothing above it needs to
know which adapters were chosen.

## Job lifecycle

```
queued -> processing -> completed
                      -> failed
```

`queued` and `processing` are the only states a job can leave; `completed`
and `failed` are terminal. The full transition table lives in
`partikkelspredning.domain.jobs.ALLOWED_TRANSITIONS` and is enforced by
`SimulationJob.transition_status` - nothing else assigns to `job.status`
directly.

**If a worker claims a job and disappears:** this iteration does not
implement a lease/timeout/retry mechanism. `SimulationJob` already carries
`worker_id` and `claimed_at` so that a future mechanism (e.g. "return to
`queued` if still `processing` after N minutes with no completion") can be
added without a data migration. The Azure Storage Queue adapter's
visibility timeout already gives a basic form of this for the *claim* step
itself (an unacknowledged claim becomes reclaimable once the timeout
expires); the local CSV queue adapter does not.

## Parameter definitions

`POST /jobs` accepts `parameters` as an arbitrary JSON object - there is
**no predefined, server-configured parameter schema** it validates against.
Any job with any shape of parameters is accepted and queued; whether a job
is actually runnable is for the (not-yet-implemented) compute server to
decide once it claims it (see "How the compute server is expected to
interact with the API" below).

`partikkelspredning.domain.parameters.ParameterDefinition` (`name`, `type`,
`description`; only `integer`, `float`, and `text` types are supported)
exists purely to describe the fields of *one* generated form. `POST /form`
takes a list of these directly in its request body and renders a
standalone, dependency-free HTML page for that specific parameter set (e.g.
resolution/duration/experiment) - a static-site-generator convenience, not
something this repo deploys or hosts. Its output has no bearing on what
`POST /jobs` will accept: a form generated for one parameter list, and a
job submitted with entirely different parameters, are both valid as far as
this backend is concerned.

## API

Interactive OpenAPI docs are available at `/docs` (FastAPI's default) when
running locally via `uvicorn`. The deployed Azure Function App serves the
same endpoints (see "Azure deployment" below) but has no such docs page,
since it isn't hosting the FastAPI app.

| Method & path | Purpose |
|---|---|
| `POST /jobs` | Submit a new job: `{user_email, parameters, metadata?}` -> `{job_id, status, ...}` |
| `GET /jobs/{job_id}` | Get a job's current state. Unknown id -> 404. |
| `POST /jobs/claim` | For the future compute server: atomically claim one queued job. `{worker_id}` -> the job, or 204 if none available. |
| `POST /jobs/{job_id}/complete` | For the future compute server: report success. `{worker_id, result_reference}`. |
| `POST /jobs/{job_id}/fail` | For the future compute server: report failure. `{worker_id, error_message}`. |
| `POST /form` | Generate a standalone HTML submission form from `{parameters, title?}`. |

`claim`/`complete`/`fail` are the interface the (not-yet-implemented)
compute server will use; see Security below for how they're expected to
gain authentication later.

## How the compute server is expected to interact with the API

1. Poll `POST /jobs/claim` with its own `worker_id`.
2. On 200, run the simulation using the returned `parameters`.
3. On success, write the result somewhere the configured `ResultStore`
   adapter understands (a local path, an Azure Blob), then call
   `POST /jobs/{job_id}/complete` with that `result_reference` and the same
   `worker_id`.
4. On failure, call `POST /jobs/{job_id}/fail` with an `error_message` and
   the same `worker_id`.

None of this is implemented in this repository - only the endpoints it will
call.

## Vendor independence / dependency injection

`PARTIKKEL_STORAGE_MODE` (`local` or `azure`) selects the adapter set;
`partikkelspredning.composition.build_job_service` is the only code that
imports both adapter families and chooses between them. This is orthogonal
to *hosting* (uvicorn vs. Azure Functions) - you can, for instance, run the
FastAPI app locally with `uvicorn` against real Azure Storage by setting
`PARTIKKEL_STORAGE_MODE=azure` locally.

## Configuration

All configuration is via environment variables (see
`src/partikkelspredning/config.py`) - no resource names or credentials are
hard-coded:

| Variable | Meaning | Default |
|---|---|---|
| `PARTIKKEL_STORAGE_MODE` | `local` or `azure` | `local` |
| `PARTIKKEL_API_BASE_URL` | API base URL baked into generated forms | `http://localhost:8000` |
| `PARTIKKEL_LOCAL_DATA_DIR` | local mode: where CSV/results files live | `./data` |
| `AZURE_STORAGE_CONNECTION_STRING` | azure mode: shared connection string | *(required in azure mode)* |
| `PARTIKKEL_AZURE_TABLE_NAME` | azure mode: job metadata table | `jobs` |
| `PARTIKKEL_AZURE_QUEUE_NAME` | azure mode: job queue | `jobs` |
| `PARTIKKEL_AZURE_RESULTS_CONTAINER` | azure mode: results blob container | `results` |

## Security

This is a prototype; the following is deliberately minimal but not ignored:

* Request structure is validated server-side (Pydantic models: e.g.
  `user_email` must be a well-formed email address). Job `parameters`
  content itself is *not* validated against any schema - see "Parameter
  definitions" above for why, and note this means the compute server that
  eventually claims a job must treat its parameters as untrusted input too.
* Job IDs are server-generated (`uuid4`); a client-supplied `job_id` in a
  URL is only ever used to look up a job (404 if unknown) - it is never
  trusted to grant any special permission.
* No storage credentials or other secrets are ever returned by the API or
  hard-coded in source; they're read from environment variables (see
  Configuration).
* `claim`/`complete`/`fail` - the endpoints the future compute server calls
  - have **no authentication yet**. Each depends on
  `partikkelspredning.api.security.require_worker_auth`, currently a no-op,
  specifically so real authentication (an API key, mTLS, ...) can be added
  in one place later without touching route logic.
* `JobService` additionally checks that only the worker that claimed a job
  can complete/fail it (`JobOwnershipError`) - a correctness safeguard
  against bugs, not a substitute for real authentication.

## Running locally

```bash
pip install -e ".[dev,local]"
uvicorn partikkelspredning.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API docs.

### How CSV persistence works

In `local` mode (the default), `partikkelspredning.adapters.local`:

* stores job metadata/state as rows in `PARTIKKEL_LOCAL_DATA_DIR/jobs.csv`
  (via pandas),
* stores the queue as one job id per line in
  `PARTIKKEL_LOCAL_DATA_DIR/queue.txt`,
* stores results under `PARTIKKEL_LOCAL_DATA_DIR/results/`, and
* logs notifications to the console instead of sending email.

Both CSV-backed files are guarded by an `fcntl`-based exclusive file lock
around each read-modify-write, so a local process (or a few concurrent
ones, as in tests) behaves predictably. This is intentionally simple and
not meant to become a production database - see `adapters/azure/` for that.

### Generating the static form

```bash
curl -X POST http://localhost:8000/form \
  -H "Content-Type: application/json" \
  -d '{"parameters": [
        {"name": "resolution", "type": "integer", "description": "Horizontal grid resolution"},
        {"name": "duration", "type": "float", "description": "Simulation duration in days"},
        {"name": "experiment", "type": "text", "description": "Name of the experiment"}
      ]}' \
  -o form.html
```

`form.html` is a complete, dependency-free page - open it directly in a
browser. It submits to `PARTIKKEL_API_BASE_URL`'s `/jobs` endpoint, so
regenerate it if that URL changes.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Covers (with no Azure credentials or SDKs required):

* parameter validation (valid, invalid, type coercion)
* job creation and every state transition, including rejected ones
* claiming queued jobs and preventing duplicate claims
* completing and failing jobs, including notification and ownership checks
* the local CSV repository and queue adapters
* a small number of FastAPI endpoint tests

Optional Azure integration tests live in `tests/azure_integration/` behind
the `azure_integration` pytest marker (excluded by default - see
`pyproject.toml`'s `addopts`). Run them explicitly against a real or
[Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite)-emulated
storage account:

```bash
pip install -e ".[azure]"
AZURE_STORAGE_CONNECTION_STRING="..." pytest -m azure_integration
```

## Azure deployment

See [`api/README.md`](api/README.md) for how `api/function_app.py`'s
HTTP-triggered functions expose this application inside Azure Functions,
and how to deploy it.

## Scope of this iteration

Implemented: job submission, validation, the queued/processing/completed/failed
lifecycle, claim/complete/fail endpoints, static form generation, local and
Azure adapters for storage.

**Not implemented** (see the project brief): the compute server / ocean
model itself, real email delivery, sophisticated authentication, a
lease/retry mechanism for stale claims, and anything Kubernetes-related.
This iteration's goal is a clean, small architecture for job submission and
state management that the rest of the system can grow into.
