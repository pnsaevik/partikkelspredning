# Partikkelspredning - job submission backend

The job-submission/tracking backend for a future particle-dispersion
simulation system. A client submits simulation parameters as an arbitrary
JSON object - there is no predefined parameter schema this backend
validates against; it accepts and stores the job as queued. A future
compute server (**not implemented here**) will claim queued jobs and is the
one that decides whether a given job's parameters are actually runnable,
then reports completion or failure back. A small registry of named,
pre-configured forms (`GET /`, `GET /forms`) lets an operator discover and
submit standard experiments without knowing URLs or parameter sets in
advance; a form's shape has no bearing on what `POST /jobs` will accept.

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
                          │   form_registry,            │
                          │   form_renderer)             │
                          └──────┬───────────────┬─────┘
                                 │ uses           │ uses
                     ┌───────────▼───┐      ┌─────▼───────────┐
                     │  domain/       │      │  ports/  (Protocols)│
                     │  SimulationJob,│      │  JobRepository,      │
                     │  JobStatus,    │      │  JobQueue,            │
                     │  parameters,   │      │  ResultStore,          │
                     │  forms         │      │  NotificationService,  │
                     │                │      │  FormStore             │
                     └────────────────┘      └──────────┬─────────────┘
                                 implemented by ┌─────────┴─────────┐
                                                │                   │
                                     ┌──────────▼───────┐ ┌─────────▼─────────┐
                                     │ adapters/local/   │ │ adapters/azure/    │
                                     │ FormStore only     │ │ Table Storage,      │
                                     │ (no cloud creds)   │ │ Storage Queue,       │
                                     │                     │ │ Blob Storage,        │
                                     │                     │ │ incl. FormStore      │
                                     └───────────────────┘ └─────────────────────┘
```

Azure Functions is the only real hosting target
(`api/function_app.py`, HTTP-triggered functions calling straight into
`JobService`/the forms registry). The FastAPI app
(`partikkelspredning.api.app`) still exists, but only so
`tests/test_api.py` can exercise the same routing/schema behavior via
`TestClient` - there is no local, uvicorn-hosted deployment target any
more. Both share the same request/response schemas and domain error
handling, so the two can't drift apart on anything but HTTP transport; the
FastAPI app additionally gets interactive `/docs` "for free" (see "API"
below), which the Function App has no equivalent of.

### Separation of concerns

| Layer | Path | May import |
|---|---|---|
| Domain | `src/partikkelspredning/domain/` | pydantic only |
| Services | `src/partikkelspredning/services/` | domain, ports |
| Ports | `src/partikkelspredning/ports/` | domain (typing only) |
| Local adapters | `src/partikkelspredning/adapters/local/` | domain, ports |
| Azure adapters | `src/partikkelspredning/adapters/azure/` | domain, ports, `azure.*` |
| API | `src/partikkelspredning/api/` | everything above, FastAPI |
| Azure Functions | `api/function_app.py` | `partikkelspredning`, `azure.functions` |

**`domain/`, `services/`, and `ports/` contain no `azure`, `azure-functions`,
or `fastapi` imports.** `partikkelspredning.composition` is the one place
("composition root") that picks concrete adapters based on configuration
and wires them into a `JobService`/`FormStore`; nothing above it needs to
know which adapters were chosen. Job storage (repository, queue, result
store, notifications) is always Azure - there is no local adapter for it;
`adapters/local/` now holds only a filesystem `FormStore`, used for local
development and the default test suite's coverage of the forms registry.

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
expires).

## Parameter definitions

`POST /jobs` accepts `parameters` as an arbitrary JSON object - there is
**no predefined, server-configured parameter schema** it validates against.
Any job with any shape of parameters is accepted and queued; whether a job
is actually runnable is for the (not-yet-implemented) compute server to
decide once it claims it (see "How the compute server is expected to
interact with the API" below).

`partikkelspredning.domain.parameters.ParameterDefinition` (`name`, `type`,
`description`; only `integer`, `float`, and `text` types are supported)
exists purely to describe the fields of one generated form.
`partikkelspredning.domain.forms.Form` pairs a set of these with an id,
name, and description - the shape of one entry in the forms registry (see
"Multiple forms registry" below). Its output has no bearing on what
`POST /jobs` will accept: a form generated for one parameter list, and a
job submitted with entirely different parameters, are both valid as far as
this backend is concerned.

## API

Interactive OpenAPI docs are available at `/docs` (FastAPI's default) if you
run the FastAPI app (`partikkelspredning.api.app:create_app`) yourself, e.g.
with a locally-installed `uvicorn` - this app isn't deployed anywhere by
this repo (see "Architecture" above), it exists for `tests/test_api.py`.
The deployed Azure Function App serves the same endpoints (see "Azure
deployment" below) but has no such docs page.

| Method & path | Purpose |
|---|---|
| `GET /` | Landing page listing every pre-configured form, linking to its pre-rendered HTML page. |
| `GET /forms` | The same forms as JSON, for programmatic access: id, name, description, parameters, url. |
| `POST /jobs` | Submit a new job: `{user_email, parameters, metadata?}` -> `{job_id, status, ...}` |
| `GET /jobs/{job_id}` | Get a job's current state. Unknown id -> 404. |
| `POST /jobs/claim` | For the future compute server: atomically claim one queued job. `{worker_id}` -> the job, or 204 if none available. |
| `POST /jobs/{job_id}/complete` | For the future compute server: report success. `{worker_id, result_reference}`. |
| `POST /jobs/{job_id}/fail` | For the future compute server: report failure. `{worker_id, error_message}`. |

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

Job storage (repository, queue, result store, notifications) is always
Azure - `partikkelspredning.composition.build_job_service` always builds
the real Azure adapters and requires `AZURE_STORAGE_CONNECTION_STRING`.
`PARTIKKEL_STORAGE_MODE` (`local`, the default, or `azure`) instead selects
where *pre-rendered forms* are stored: `build_forms_store` returns a
filesystem-backed `FormStore` in `local` mode (no cloud credentials
needed) or a Blob Storage-backed one in `azure` mode.

## Configuration

All configuration is via environment variables (see
`src/partikkelspredning/config.py`) - no resource names or credentials are
hard-coded:

| Variable | Meaning | Default |
|---|---|---|
| `PARTIKKEL_STORAGE_MODE` | `local` or `azure` - selects **forms** storage only (job storage is always Azure) | `local` |
| `PARTIKKEL_API_BASE_URL` | API base URL baked into generated forms | `http://localhost:8000` |
| `PARTIKKEL_FORMS_LOCAL_DIR` | local mode: where pre-rendered forms are written | `./data/forms` |
| `AZURE_STORAGE_CONNECTION_STRING` | shared connection string - **always required** for job storage; also required when `PARTIKKEL_STORAGE_MODE=azure` | *(required)* |
| `PARTIKKEL_AZURE_TABLE_NAME` | azure mode: job metadata table | `jobs` |
| `PARTIKKEL_AZURE_QUEUE_NAME` | azure mode: job queue | `jobs` |
| `PARTIKKEL_AZURE_RESULTS_CONTAINER` | azure mode: results blob container | `results` |
| `PARTIKKEL_AZURE_FORMS_CONTAINER` | azure mode: public forms blob container | `forms` |

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
* The one exception to "no public storage" is the public job-submission
  form's blob container (see "Deploying the public job-submission form"
  above): it is intentionally created with anonymous read access, since it
  holds only a static, non-secret HTML page.

## Running locally

Azure Functions is the only real hosting target - see
[`api/README.md`](api/README.md)'s "Run locally" section for the
[Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
setup (`func start`). Job storage needs a real (or
[Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite)-emulated)
Azure Storage account even for local `func start` - there is no local job
storage any more (see "Vendor independence" above).

```bash
pip install -e ".[dev]"
```

installs everything needed to run the test suite (which uses fakes and a
local `FormStore`, no Azure account needed - see "Tests" below).

### Multiple forms registry

`src/partikkelspredning/forms/definitions.json` lists named,
pre-configured forms (id, name, description, parameters - see
`partikkelspredning.domain.forms.Form`). At startup,
`partikkelspredning.services.form_registry.load_forms` parses that file and
`services.form_renderer.prerender_and_store` renders + uploads each one via
the configured `FormStore` (local disk or Azure Blob Storage, see
"Configuration" above) - a malformed registry or unreachable store fails
startup outright rather than surfacing later. `GET /` then serves a
pre-rendered index page linking to each form, and `GET /forms` serves the
same data as JSON, including each form's URL. Forms are source-code-only in
this iteration - adding one means editing `definitions.json` and
redeploying, there's no admin endpoint yet.

### Deploying the public job-submission form

Separately from the `/form` endpoint above, a single fixed parameter set
(`resolution`, `duration`) can be deployed as a public, standalone HTML page
in Azure Blob Storage, so external users can submit a job without calling
the API directly - the notification email is collected by the standard
`user_email` field every generated form already has, so it isn't repeated
as its own parameter. This is Azure-only (no local-mode target) and is
triggered manually, not by an HTTP endpoint:

```bash
pip install -e ".[azure]"
PARTIKKEL_STORAGE_MODE=azure AZURE_STORAGE_CONNECTION_STRING="..." \
  python scripts/deploy_public_form.py
```

Prints the deployed form's public URL on success. The form is uploaded to
the `PARTIKKEL_AZURE_FORMS_CONTAINER` container (see Configuration above),
created with public (anonymous) read access - the page is static and
non-secret, so this is an intentional exception to the rest of this
project's "no public storage" posture (see Security below).

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
* the forms registry: loading/validating `definitions.json`, rendering,
  the local and Azure `FormStore` selection
* a small number of FastAPI endpoint tests and `api/function_app.py`
  Azure Functions handler tests, both using a fakes-backed `JobService`

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
lifecycle, claim/complete/fail endpoints, a multiple-forms registry
pre-rendered at startup (`GET /`, `GET /forms`), a manually-deployed public
job-submission form on Azure Blob Storage, Azure adapters for job storage,
and local/Azure adapters for forms storage.

**Not implemented** (see the project brief): the compute server / ocean
model itself, real email delivery, sophisticated authentication, a
lease/retry mechanism for stale claims, and anything Kubernetes-related.
This iteration's goal is a clean, small architecture for job submission and
state management that the rest of the system can grow into.
