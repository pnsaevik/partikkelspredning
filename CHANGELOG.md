# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.11] - 2026-09-15

### Removed

- `FEATURE_PLAN.md` - a Phase 1 planning artifact for the merged
  `multiple_forms` feature branch, left in `main` by mistake (the previous
  feature removed its own copy before merging; this one didn't).

## [0.1.10] - 2026-09-15

### Added

- Multiple forms registry: `src/partikkelspredning/forms/definitions.json`
  lists named, pre-configured forms (id, name, description, parameters -
  `domain.forms.Form`), loaded and validated at startup by
  `services.form_registry.load_forms` (fail-fast on a malformed file,
  missing fields, or duplicate ids). Each form is rendered and uploaded via
  a `FormStore` once, at startup (`services.form_renderer
  .prerender_and_store`), rather than generated per request. `GET /`
  serves a pre-rendered landing page linking to every form; `GET /forms`
  serves the same data as JSON (id, name, description, parameters, url)
  for programmatic access. Both are implemented identically in the FastAPI
  app (`api.routes_index`, used only by `tests/test_api.py`) and in
  `api/function_app.py`'s Azure Functions handlers.
- `composition.build_forms_store` and `adapters/local/form_store.py`'s
  `LocalFormStore`: the forms registry's `FormStore` is selected by
  `PARTIKKEL_STORAGE_MODE` - `local` (default) writes pre-rendered HTML to
  `PARTIKKEL_FORMS_LOCAL_DIR` (new setting, default `./data/forms`) with no
  cloud credentials needed; `azure` reuses the existing `BlobFormStore`/
  `PARTIKKEL_AZURE_FORMS_CONTAINER`. Separate from - and unrelated to -
  `build_form_store`, which still deploys only the pre-existing single
  public job-submission form and is unchanged.
- `deploy_staging.yml`'s new `azure_integration` job: after each staging
  deploy, runs the pre-existing (opt-in, previously CI-untested)
  `tests/azure_integration/` suite against the real
  `partikkelspredning-api-staging` storage account, using a new
  `staging`-environment secret `AZURE_STORAGE_CONNECTION_STRING` (one-time
  setup, see `api/README.md`). Skips gracefully if that secret isn't set.
  The default `pytest` run (`workflow_push.yml` included) still always
  skips `azure_integration`-marked tests, unchanged.

### Fixed

- `GET /` (the forms registry's landing page) never actually reached
  `function_app.py`'s `index` function when deployed - found by manually
  testing the deployed staging app. Two things were both required, neither
  sufficient alone: `AzureWebJobsDisableHomepage=true` as an app setting
  (`action_deploy.yml` now sets it automatically on every deploy - new
  `resource-group` input, defaulting to `partikkelspredning-rg`;
  `deploy_staging.yml` passes `partikkelspredning-staging-rg`), *and* the
  function's own route changed from `""` to `"/"` - with only the app
  setting, Azure returned a bare `204` for `GET /` instead of routing to
  the function; with neither, it silently served Azure's generic "Your
  Azure Function App is up and running." placeholder instead. A new
  smoke-test step in `action_deploy.yml` now verifies `GET /` actually
  serves the index page on every deploy (not just `/health`, which
  wouldn't have caught this).

### Removed

- **Local job storage and the local, uvicorn-hosted deployment mode.**
  `adapters/local/csv_repository.py`, `csv_queue.py`,
  `filesystem_result_store.py`, `console_notifications.py`, and
  `src/partikkelspredning/main.py` are gone; `pandas` and the `local`
  pyproject extra (`uvicorn[standard]`) are no longer dependencies. Job
  storage (repository, queue, result store, notifications) is now
  unconditionally the real Azure adapters - `build_job_service` always
  requires `AZURE_STORAGE_CONNECTION_STRING`, regardless of
  `PARTIKKEL_STORAGE_MODE` (which now only selects *forms* storage, see
  above). **Azure Functions (`func start` / a deployed Function App) is
  the only way to run this application for real now** - the FastAPI app
  (`partikkelspredning.api.app`) still exists, but solely so
  `tests/test_api.py` can exercise the same HTTP routing/schema behavior
  via `TestClient`; it is never deployed. `PARTIKKEL_LOCAL_DATA_DIR` is
  removed (see `PARTIKKEL_FORMS_LOCAL_DIR` above).
- The dynamic `POST /form` endpoint (generate-any-parameter-set-on-demand)
  is superseded by the pre-rendered forms registry above and removed,
  along with `api.schemas.FormRequest`. `services.form_renderer
  .generate_form_html` (renamed from `services.form_service
  .generate_form_html`, same behavior) is unaffected and still used by the
  forms registry and the unrelated `public_form_service`.

## [0.1.9] - 2026-09-15

### Added

- Public job-submission form: a fixed parameter set (`resolution`,
  `duration`) can now be rendered and deployed as a standalone,
  publicly-readable HTML page in Azure Blob Storage, via
  `scripts/deploy_public_form.py` (Azure-only for this iteration - no local
  fallback). Adds a new `FormStore` port, `BlobFormStore` adapter (uploads
  to a container created with public blob-level read access),
  `domain.public_forms.PUBLIC_FORM_PARAMETERS`, and
  `services.public_form_service.deploy_public_form`, plus the new
  `PARTIKKEL_AZURE_FORMS_CONTAINER` setting (default `forms`). The
  notification email is collected by the standard `user_email` field every
  generated form already has, rather than a separate, redundant `email`
  parameter (an early draft included one; dropped after testing the
  deployed form on staging showed it duplicating that field). Unrelated to
  the existing `POST /form` endpoint, which still renders any parameter set
  on demand without deploying it anywhere.
- A `staging` deployment target for trying out Azure-specific behavior
  before merging: `deploy_staging.yml` runs on every push to a branch with
  an open PR into `main` (and can also be triggered by hand for a branch
  with no PR yet: `gh workflow run deploy_staging.yml --ref <branch>`),
  deploying `api/` to a new, separate `partikkelspredning-api-staging`
  Function App with its own resource group and storage account, so it can
  never touch production data. `action_deploy.yml` now takes `app-name`/
  `environment` inputs (defaulting to the existing production values, so
  `deploy.yml` needed no changes) to let both workflows share the same
  deploy logic. See `api/README.md`'s "Continuous integration and
  deployment" section for the one-time OIDC/environment setup this needed.

## [0.1.8] - 2026-09-14

### Changed

- Replaced `api/function_app.py`'s `func.AsgiFunctionApp` hosting of the
  FastAPI app with explicit HTTP-triggered Azure Functions, one per
  endpoint (`jobs`, `jobs/{job_id}`, `jobs/claim`,
  `jobs/{job_id}/complete`, `jobs/{job_id}/fail`, `form`). Each is a thin
  wrapper that translates `azure.functions.HttpRequest`/`HttpResponse`
  straight into calls on the same `JobService` the FastAPI routes use,
  reusing the same request/response schemas
  (`partikkelspredning.api.schemas`) and domain error handling - no
  business logic is duplicated between the two hosting modes.
- Added `GET /health`, a liveness check with no FastAPI equivalent, and
  pointed the deploy workflow's smoke test at it instead of
  `/openapi.json` (which only the FastAPI app serves).
- Added `tests/test_function_app.py`, unit-testing the new functions
  directly against the real local (CSV-backed) adapters, mirroring
  `tests/test_api.py`'s coverage of the equivalent FastAPI routes.
  `azure-functions` (needed to build the `HttpRequest`/`HttpResponse`
  objects these tests use, not for any cloud access) is now part of the
  `dev` extra, and `api/` was added to `pythonpath` in `pyproject.toml` so
  tests can import `function_app`.

## [0.1.7] - 2026-09-14

### Fixed

- Found (via Application Insights, newly enabled on the Azure resource -
  see [0.1.6]'s deploy attempt for the last symptom) the actual cause of
  every persistent 503 since [0.1.2]: the Python Functions host crash-loops
  at startup with a `RoutePatternException` - `Azure/functions-action`
  deployment always succeeded and the Python worker always started fine,
  but the host's ASP.NET Core routing layer then failed to register the
  ASGI catch-all route because `host.json`'s default `routePrefix`
  (`"api"`) combined with `AsgiFunctionApp`'s route template produces the
  invalid pattern `api//{*route}` (a double slash) - a known bug,
  [Azure/azure-functions-python-worker#1310](https://github.com/Azure/azure-functions-python-worker/issues/1310).
  Every single request hit this, immediately, regardless of packaging
  mechanism ([0.1.6]) or any app code - which is why nothing on the
  application side could have fixed it. Set `extensions.http.routePrefix`
  to `""` in `api/host.json` (the confirmed workaround). The deployed app
  is now reached at the site root (e.g. `/openapi.json`, `/docs`) instead
  of under `/api/` - updated the smoke test, `PARTIKKEL_API_BASE_URL` (both
  the deployed app setting and `api/README.md`'s example), and the local
  dev docs URL accordingly. See `api/README.md`'s new "Why `routePrefix` is
  empty" section.

## [0.1.6] - 2026-09-14

### Changed

- Restored the real FastAPI/ASGI app (`api/function_app.py`), reverting the
  throwaway hello-world diagnostic from [0.1.4] now that the deploy
  pipeline itself is confirmed working.
- Replaced the vendored-wheel mechanism for installing `partikkelspredning`
  into the deployed Function App with a direct
  `partikkelspredning @ git+https://github.com/<owner>/<repo>.git@<commit>`
  line, appended to `api/requirements.txt`'s checked-out copy and pinned to
  the exact commit being deployed (`action_deploy.yml`, and the manual
  equivalent in `api/README.md`). Removes `api/build_vendor_wheel.sh` and
  the git-ignored `api/vendor/` directory entirely, along with the
  hand-maintained `partikkelspredning==<version>` pin that had to be kept
  in sync with `pyproject.toml` by hand or the install would silently fail.
  Local development now installs `partikkelspredning` separately in
  editable mode (`pip install -e ..`) instead of exercising the same
  install mechanism as deployment - the previous design's intent, but this
  needed `..` to exist, which it never does in the uploaded `api/` folder
  Azure's remote build actually runs against. Deploying manually from a
  local checkout now requires that commit to already be pushed to GitHub,
  since Kudu clones from the real repository, not the local one.

## [0.1.5] - 2026-09-14

### Fixed

- `deploy.yml`'s top-level `permissions` only granted `contents: read`, but
  the nested `deploy` job (`action_deploy.yml`, called via `uses:`)
  requests `id-token: write` for OIDC login to Azure. A reusable-workflow
  job can never be granted more permissions than the caller itself has, so
  every tag push failed at dispatch time with "The nested job 'deploy' is
  requesting 'id-token: write', but is only allowed 'id-token: none'" and
  0 jobs ever ran - a `startup_failure` invisible until a real tag push
  exercised this path (the CI restructuring in [0.1.3] was never tagged).
  Added `id-token: write` to `deploy.yml`'s top-level `permissions`.

## [0.1.4] - 2026-09-14

### Changed (temporary diagnostic)

- `v0.1.2`'s deploy to `partikkelspredning-api` (Flex Consumption) reported
  success, but the deployed app never returned 200 - `/api/openapi.json`
  stayed at 503 through the full smoke-test retry window. To isolate
  whether the Flex Consumption app can run *anything* before debugging the
  full app further, `api/function_app.py` (the FastAPI/ASGI host) is
  temporarily moved aside to `api/function_app_fastapi.py.disabled` and
  replaced with a minimal `GET /api/hello` returning "Hello, world!" -
  no FastAPI, no ASGI, no `partikkelspredning` import, no Azure SDKs.
  `api/requirements.txt` is trimmed to just `azure-functions` accordingly.
  Revert this entry's commit to restore the real app once the underlying
  issue is understood.

## [0.1.3] - 2026-09-14

### Added

- CI restructured around three gates, adapted from
  [ladim](https://github.com/pnsaevik/ladim)'s workflow philosophy: every
  push (any branch) runs `pytest` (`workflow_push.yml`); every pull request
  into `main` checks that `pyproject.toml`'s version was bumped and that
  `CHANGELOG.md` has a matching entry (`workflow_pr_main.yml`,
  `.github/scripts/version.sh`, `.github/scripts/changelog.sh` - ladim's
  originals read `ladim/__init__.py`'s `__version__` instead of
  `pyproject.toml`); a tag push only deploys if the tagged commit is
  reachable from `main` (`deploy.yml`'s new "Verify tag" job). Shared logic
  now lives in reusable `action_pytest.yml`, `action_changelog.yml`, and
  `action_deploy.yml` workflows.

## [0.1.2] - 2026-09-14

### Added

- `.github/workflows/deploy.yml`: pushing a tag matching `vX.Y.Z` runs the
  test suite, then deploys `api/` to the `partikkelspredning-api` Azure
  Function App (authenticating via OIDC, no stored secret) if the tag
  matches `pyproject.toml`'s version. See api/README.md's "Continuous
  deployment" section for one-time setup.
- A post-deploy smoke-test step in that workflow, polling
  `/api/openapi.json` for a 200 response.

### Fixed

- The deploy workflow used `scm-do-build-during-deployment` /
  `enable-oryx-build`, the classic Consumption/Premium plan build inputs,
  against `partikkelspredning-api`'s Flex Consumption plan. Flex
  Consumption needs `remote-build: true` instead - without it, Kudu
  silently skipped the Oryx build, nothing in `requirements.txt` got
  installed, and the deployed app served zero functions even though the
  workflow reported success.

## [0.1.1] - 2026-09-14

### Changed

- `POST /jobs` no longer validates submitted parameters against a
  predefined, server-configured schema — `parameters` is now accepted as an
  arbitrary JSON object and stored as-is. Whether a job is actually
  runnable is for the (not-yet-implemented) compute server to decide once
  it claims it, not this API. Removed accordingly: `validate_parameters`,
  `ParameterValidationError`, `PARTIKKEL_PARAMETER_DEFINITIONS_PATH`, and
  `JobService`'s `parameter_definitions` constructor argument.
  `partikkelspredning.domain.parameters.ParameterDefinition` remains, but
  now exists solely to describe the fields of one form generated by
  `POST /form` — a static-site-generator convenience unrelated to job
  validation.

### Fixed

- `func azure functionapp publish` no longer relies on an editable `-e ..`
  install that can't survive the remote build (only `api/` is uploaded,
  `..` doesn't exist there). `api/requirements.txt` now installs
  `partikkelspredning` from a wheel built into `api/vendor/` by the new
  `api/build_vendor_wheel.sh`, referenced via `--find-links`. See
  `api/README.md`'s "How local packaging works".

## [0.1.0] - 2026-09-14

### Added

- Project skeleton with `pyproject.toml` packaging metadata.
- Job-submission backend built with a ports-and-adapters (hexagonal)
  architecture: `domain/` (`SimulationJob`, `JobStatus`, parameters),
  `ports/` (`JobRepository`, `JobQueue`, `ResultStore`,
  `NotificationService` protocols), `services/` (`JobService`,
  `form_service`), and `api/` (FastAPI routes, schemas, dependency
  injection).
- Local adapters (`adapters/local/`) storing jobs as CSV files on disk
  with console logging, requiring no cloud credentials.
- Azure Functions adapter (`adapters/azure/`) hosting the same FastAPI
  app via ASGI, backed by Azure Table Storage, Storage Queue, and Blob
  Storage.
- Test suite covering the platform-agnostic core, with Azure
  integration tests marked and excluded by default.

### Fixed

- Suppressed Starlette's internal `anyio.abc.BlockingPortal` deprecation
  warning raised by an anyio/Starlette version mismatch outside this
  project's control.
