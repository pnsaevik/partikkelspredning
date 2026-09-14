# API stub - Azure Functions adapter

This folder is a thin Azure Functions **adapter**: it is one of only two
places (besides [`../src/partikkelspredning/adapters/azure/`](../src/partikkelspredning/adapters/azure))
that import Azure SDKs. `function_app.py` declares one HTTP-triggered Azure
Function per endpoint; each is a thin wrapper that translates between
`azure.functions.HttpRequest`/`HttpResponse` and `JobService` - the same
service class `partikkelspredning.api.routes_jobs`/`routes_form` call for
local, uvicorn-hosted development (see `function_app.py`'s module
docstring). See [the root README](../README.md) for the full architecture.

## Run locally

Requires the [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
and a Python version supported by the Azure Functions Python worker (3.9-3.12).

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ..   # partikkelspredning itself, editable - see "How packaging works" below
func start
```

The same endpoints as running `uvicorn` directly are then available at
`http://localhost:7071` (see the root README) - `host.json` sets
`extensions.http.routePrefix` to `""` (no `/api` prefix) so the routes match
exactly, including `GET /health` (a liveness check with no equivalent in
the FastAPI app, used by the deploy workflow's smoke test below).

`local.settings.json` defaults `PARTIKKEL_STORAGE_MODE` to `local`, so
`func start` works with no Azure Storage account for the *application's
own* data - CSV files are written under `PARTIKKEL_LOCAL_DATA_DIR`. Note
that `AzureWebJobsStorage` (required by the Functions *host* itself, not by
our code) is left blank here; a real deployment needs it set, either to a
real storage account connection string or `UseDevelopmentStorage=true`
against the [Azurite emulator](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

## Continuous integration and deployment (GitHub Actions)

CI is split into three gates:

* **Every push**, any branch (`workflow_push.yml`): runs the test suite
  (`action_pytest.yml`), including `tests/test_function_app.py`'s direct
  unit tests of the functions in `function_app.py`.
* **Every pull request into `main`** (`workflow_pr_main.yml`): checks that
  `pyproject.toml`'s `[project].version` was bumped - and not decreased -
  relative to the PR's base, and that `CHANGELOG.md` has a `## [<that
  version>] - ...` entry (`action_changelog.yml`, backed by
  `.github/scripts/version.sh` and `.github/scripts/changelog.sh`).
* **Pushing a tag matching `vX.Y.Z`** (e.g. `v0.1.2`) triggers
  `deploy.yml`: it first verifies the tag's commit is actually reachable
  from `main` and that the tag matches `pyproject.toml`'s version (refusing
  otherwise), then runs the test suite and, if that passes, deploys `api/`
  to the `partikkelspredning-api` Function App the same way the manual
  steps below do (pin `partikkelspredning` to this commit, then a
  remote-build deploy, `action_deploy.yml`) - no local `func` install or
  Cloud Shell needed for routine releases. `deploy.yml` can also be run
  on demand against any branch (`gh workflow run deploy.yml --ref
  <branch>`), skipping the tag checks, to test a deploy before merging.

The workflow authenticates to Azure via OIDC (a federated credential on an
Azure AD app registration scoped to this repo's `production` GitHub
environment) rather than a stored long-lived secret. One-time setup for a
new deployment target, already done for `partikkelspredning-api`:

1. In the Azure AD tenant: an app registration + service principal, with a
   federated credential (`repo:<org>/<repo>:environment:production`,
   issuer `https://token.actions.githubusercontent.com`) and a *Website
   Contributor* role assignment scoped to the function app's resource
   group (not broader - it doesn't need access to unrelated resources).
2. In the GitHub repo: an environment named `production` (Settings ->
   Environments), and repository variables `AZURE_CLIENT_ID`,
   `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` set to that app
   registration's values (Settings -> Secrets and variables -> Actions ->
   Variables tab - these identify the app registration but aren't secrets
   themselves, since OIDC needs no client secret).

The manual steps below remain useful for a first-time deploy to a new
Function App, or for deploying from a local checkout without waiting on CI.

## Deploy to Azure

```bash
# one-time setup, if the resources don't exist yet
az login
az group create --name <resource-group> --location <region>
az storage account create --name <storage-account> --resource-group <resource-group> --sku Standard_LRS
az functionapp create --resource-group <resource-group> --consumption-plan-location <region> \
  --runtime python --runtime-version <3.x> --functions-version 4 \
  --name <function-app-name> --storage-account <storage-account> --os-type Linux

# app settings for the *application's* own storage mode (separate from
# AzureWebJobsStorage, which the Functions host manages itself)
az functionapp config appsettings set --name <function-app-name> --resource-group <resource-group> \
  --settings PARTIKKEL_STORAGE_MODE=azure AZURE_STORAGE_CONNECTION_STRING="<connection-string>" \
             PARTIKKEL_API_BASE_URL="https://<function-app-name>.azurewebsites.net"

# deploy this folder's code - must be pushed to GitHub first (see below)
cd api
echo "partikkelspredning @ git+https://github.com/pnsaevik/partikkelspredning.git@$(git rev-parse HEAD)" >> requirements.txt
func azure functionapp publish <function-app-name>
git checkout -- requirements.txt   # discard the local edit above
```

`local.settings.json` is for local development only - it is git-ignored and
never deployed (see `.funcignore`); app settings for the deployed function
are configured on the Azure resource itself, as above.

### How packaging works

`func azure functionapp publish` only uploads this `api/` folder for its
remote build (it zips whatever directory contains `host.json`, filtered by
`.funcignore`) - the repo root, and everything under `../src/`, never leave
your machine as part of that build context. So `partikkelspredning` can't be
installed the way a normal sibling-package dependency would be.

Instead, `requirements.txt` installs it straight from GitHub - append a
`partikkelspredning @ git+https://github.com/<owner>/<repo>.git@<commit>`
line (as above) pinned to the exact commit being deployed, right before
`func azure functionapp publish` runs, and discard that edit afterward so
it never gets committed (`action_deploy.yml` does the same for CI-driven
deploys, pinned to `github.sha`). This needs that commit already pushed to
GitHub - Kudu clones from the real repository, not your local checkout -
so push first. Pinning to a commit rather than a version string means it
can never silently drift out of sync the way a hand-maintained version pin
could. For local development, install `partikkelspredning` separately in
editable mode instead (`pip install -e ..`, see "Run locally" above) -
there's no wheel to build and no `vendor/` directory to keep in sync.
