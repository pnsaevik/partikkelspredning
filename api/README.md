# API stub - Azure Functions adapter

This folder is a thin Azure Functions **adapter**: it is one of only two
places (besides [`../src/partikkelspredning/adapters/azure/`](../src/partikkelspredning/adapters/azure))
that import Azure SDKs. `function_app.py` declares one HTTP-triggered Azure
Function per endpoint; each is a thin wrapper that translates between
`azure.functions.HttpRequest`/`HttpResponse` and `JobService`/the forms
registry - the same services `partikkelspredning.api.routes_jobs`/
`routes_index` call for the FastAPI app that `tests/test_api.py` exercises
directly (see `function_app.py`'s module docstring). Azure Functions is the
only real hosting target for this application - there is no local,
uvicorn-hosted deployment any more. See [the root README](../README.md) for
the full architecture.

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

The same endpoints are available at `http://localhost:7071` (see the root
README) - `host.json` sets `extensions.http.routePrefix` to `""` (no `/api`
prefix) so the routes match exactly, including `GET /health` (a liveness
check with no equivalent in the FastAPI app, used by the deploy workflow's
smoke test below).

Job storage is always Azure - there is no local fallback - so `func start`
needs a real `AZURE_STORAGE_CONNECTION_STRING` set in `local.settings.json`
even for local development (a real storage account, or the
[Azurite emulator](https://learn.microsoft.com/azure/storage/common/storage-use-azurite)
with `UseDevelopmentStorage=true`). `local.settings.json` defaults
`PARTIKKEL_STORAGE_MODE` to `local`, which only affects *forms* storage:
pre-rendered forms are written under `PARTIKKEL_FORMS_LOCAL_DIR` instead of
Azure Blob Storage, so trying out the forms registry (`GET /`, `GET
/forms`) needs no separate container. Note that `AzureWebJobsStorage`
(required by the Functions *host* itself, not by our code) is left blank
in the checked-in template; a real deployment needs it set the same way.

## Continuous integration and deployment (GitHub Actions)

CI is split into four gates:

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

`action_deploy.yml` (the reusable workflow that actually does the deploy)
takes `app-name`/`environment` inputs, defaulting to `partikkelspredning-api`
/ `production` - so `deploy.yml` itself needs no changes to keep deploying
there. `deploy_staging.yml` calls the same reusable workflow with those
inputs overridden to target a second, entirely separate Function App:

* **Every push to a branch with an open PR into `main`** (`deploy_staging.yml`,
  `pull_request`'s `synchronize` event - also runnable by hand for a branch
  with no PR yet: `gh workflow run deploy_staging.yml --ref <branch>`):
  deploys `api/` to `partikkelspredning-api-staging` (resource group
  `partikkelspredning-staging-rg`), which has its own storage account -
  nothing it does can affect `partikkelspredning-api`'s data. Meant as a
  testbed for trying out a branch's Azure-specific behavior (e.g. the
  public form's Blob Storage upload) before merging its PR. A
  `pull_request`-triggered run uses the workflow file from the PR branch
  itself, so this works even before `deploy_staging.yml` has been merged to
  `main` - unlike `workflow_dispatch`, which GitHub only ever discovers
  from the default branch. After a successful deploy, its `azure_integration`
  job runs `tests/azure_integration/` (see the root README's "Optional
  Azure integration tests" section) against the real staging storage
  account - this is the *only* place those tests run automatically; the
  default `pytest` run (`workflow_push.yml` included) always skips them.

Both workflows authenticate to Azure via OIDC (a federated credential on an
Azure AD app registration scoped to a specific GitHub *environment* -
`production` or `staging`) rather than a stored long-lived secret. One-time
setup for a new deployment target, already done for both
`partikkelspredning-api` and `partikkelspredning-api-staging`:

1. In the Azure AD tenant: an app registration + service principal, with a
   federated credential (`repo:<org>/<repo>:environment:<production or
   staging>`, issuer `https://token.actions.githubusercontent.com`) and a
   *Website Contributor* role assignment scoped to that Function App's
   resource group only (not broader, and not shared between the two
   environments' app registrations - staging's identity has no access to
   the production resource group or vice versa).
2. In the GitHub repo: an environment named `production` or `staging`
   (Settings -> Environments), and repository variables `AZURE_CLIENT_ID`,
   `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` - scoped to that environment,
   not repository-wide, since the two environments use different app
   registrations - set to that app registration's values (Settings ->
   Secrets and variables -> Actions -> Variables tab, environment secrets
   section - these identify the app registration but aren't secrets
   themselves, since OIDC needs no client secret).
3. `staging` only, for the `azure_integration` job above: an
   `AZURE_STORAGE_CONNECTION_STRING` *secret* (not variable - this one is
   an actual secret, unlike the OIDC identifiers above) on the `staging`
   environment, set to the same connection string already configured as
   the `partikkelspredning-api-staging` Function App's own
   `AZURE_STORAGE_CONNECTION_STRING` app setting (see "Deploy to Azure"
   below). Set it from a local shell, never pasted into a chat or commit:
   `gh secret set AZURE_STORAGE_CONNECTION_STRING --env staging` (prompts
   for the value). Left unset, the `azure_integration` job's tests just
   skip (see `tests/azure_integration/test_azure_adapters.py`'s own
   `skipif`) rather than fail - so this step is optional, not required for
   deploys or the rest of CI to work.

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
             PARTIKKEL_API_BASE_URL="https://<function-app-name>.azurewebsites.net" \
             AzureWebJobsDisableHomepage=true
# ^ without this, Azure intercepts bare `GET /` with its own generic
# placeholder page before it ever reaches the forms registry's index route
# - action_deploy.yml sets this automatically on every CI-driven deploy, so
# this manual step only matters for a first deploy done outside CI.

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
