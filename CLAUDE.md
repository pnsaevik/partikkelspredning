# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Precedence:** where anything below conflicts with the general
Claude Code workflow guide, this file wins for this repo. See
"Compatibility with the general workflow guide" at the end for the specific
points where the two disagree and how they were reconciled.

## What this is

The job-submission/tracking backend for a future particle-dispersion simulation
system. `POST /jobs` accepts simulation parameters as an arbitrary JSON
object — there is no predefined parameter schema this backend validates
against — and queues the job. A future compute server (not implemented in
this repo) will claim queued jobs, decide whether a given job's parameters
are actually runnable, run the simulation, and report completion/failure
back. `GET /` and `GET /forms` serve a small registry of named,
pre-configured forms (`src/partikkelspredning/forms/definitions.json`),
pre-rendered at startup — a form's shape has no bearing on what `POST
/jobs` accepts. First deployment target is Azure, but business logic never
imports an Azure SDK. Azure Functions is the only real hosting target —
there is no local, uvicorn-hosted deployment any more; job storage
(repository, queue, result store, notifications) is always Azure, with no
local fallback.

## Commands

```bash
# install (editable, with dev extras)
pip install -e ".[dev]"

# run the full test suite
pytest

# run a single test file / test
pytest tests/test_job_service.py
pytest tests/test_job_service.py::test_name

# run the app locally (requires a real/Azurite Azure Storage account —
# job storage has no local mode; see api/README.md)
cd api && func start
```

The default `pytest` run needs no Azure credentials: job-storage-dependent
tests inject a fakes-backed `JobService` (`tests/fakes.py`) instead of the
real composition root, and the forms registry is exercised against a local
filesystem `FormStore`. Real Azure adapter behavior is covered only by the
`azure_integration`-marked tests below.

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
  -> services/ (JobService, form_registry, form_renderer)
       -> domain/ (SimulationJob, JobStatus, parameters, forms)
       -> ports/  (Protocols: JobRepository, JobQueue, ResultStore, NotificationService, FormStore)
                       implemented by:
                       adapters/local/ (FormStore only, filesystem - no cloud creds)
                       adapters/azure/ (Table Storage, Storage Queue, Blob Storage, incl. FormStore)
```

Import rules, enforced by convention (not tooling) — do not violate them:

| Layer | Path | May import |
|---|---|---|
| Domain | `src/partikkelspredning/domain/` | pydantic only |
| Services | `src/partikkelspredning/services/` | domain, ports |
| Ports | `src/partikkelspredning/ports/` | domain (typing only) |
| Local adapters | `src/partikkelspredning/adapters/local/` | domain, ports |
| Azure adapters | `src/partikkelspredning/adapters/azure/` | domain, ports, `azure.*` |
| API | `src/partikkelspredning/api/` | everything above, FastAPI |
| Azure Functions | `api/function_app.py` | `partikkelspredning`, `azure.functions` |

`domain/`, `services/`, and `ports/` must never import `azure`,
`azure-functions`, or `fastapi`. `partikkelspredning.composition` is the
sole composition root: `build_job_service` always builds the real Azure
adapters (job storage has no local mode); `build_forms_store` picks
between a local filesystem `FormStore` and an Azure Blob Storage one based
on `PARTIKKEL_STORAGE_MODE` (`local`/`azure`) for the forms registry —
nothing above either function should know which adapters were chosen.

Both hosting modes call into the *same* `services`/`domain`/`ports` layer,
never a reimplementation of the business logic — only the HTTP transport
differs. Azure Functions is the only real deployment target; the FastAPI
app (`partikkelspredning.api.app`) exists solely so `tests/test_api.py` can
exercise the same routes via `TestClient` — there is no uvicorn-hosted
local deployment:

```
FastAPI app (tests/test_api.py's TestClient only) and
Azure Functions (api/function_app.py, the real deployment target) both
call straight into the same JobService / forms-registry services.
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
generated form. `partikkelspredning.domain.forms.Form` pairs a list of
these with an id/name/description — one entry in the forms registry
(`src/partikkelspredning/forms/definitions.json`, loaded by
`services.form_registry.load_forms`, rendered and pre-served via `GET /`/
`GET /forms` — see "What this is" above). Unrelated to what `POST /jobs`
will accept.

## Configuration

All configuration is via environment variables
(`src/partikkelspredning/config.py`) — no resource names or credentials are
hard-coded. Key ones: `PARTIKKEL_STORAGE_MODE` (`local`/`azure`, default
`local` — selects **forms** storage only), `PARTIKKEL_FORMS_LOCAL_DIR`
(default `./data/forms`), `AZURE_STORAGE_CONNECTION_STRING` (**always**
required — job storage has no local mode). Full table in the root README.

`local` mode (forms storage only): `adapters/local/form_store.py`'s
`LocalFormStore` writes each pre-rendered form to
`PARTIKKEL_FORMS_LOCAL_DIR/{form_id}.html`. Job storage (metadata, queue,
results, notifications) has no local adapter any more — it is always the
real Azure adapters in `adapters/azure/`.

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

## Feature Development Workflow

### Phase 1: Exploration & Scoping (Collaborative)
1. User initiates: requests a new feature and provides the branch name
2. I create the feature branch (`feature/<name>`) from main and bump the
   `version` field in `pyproject.toml` (patch component) as the first commit
3. Discuss the feature idea until clarity emerges
4. Agree on scope and constraints (feature-scoped boundaries), including
   which architectural layer(s) the feature touches — see "Architecture"
   above; a feature that would require an import direction not in that
   table is a scope question for Phase 1, not something to route around
   during implementation
5. Draft a user story with acceptance criteria
6. Iterate until satisfaction
7. I commit the plan as **`FEATURE_PLAN.md`** containing:
   - User story and acceptance criteria
   - Feature-scoped constraints
   - Implementation notes or architectural decisions
8. Phase 1 is complete; Phase 2 begins

### Phase 2: Implementation (Autonomous)
Once `FEATURE_PLAN.md` is committed:
1. **Write tests first** (test-first approach):
   - Write the test (unit tests with mocked data)
   - Confirm it fails for the right reason
   - Do not commit yet
   - Implement the function until the test passes
2. **Before committing:**
   - Run tests locally to confirm the test passes
   - Never commit if tests are knowingly failing
   - Include clear, descriptive commit messages
3. **Commit strategy:**
   - Small-scoped commits (e.g., one per unit-tested function)
   - Each commit includes both test and implementation
   - It's acceptable to have minor issues in early commits; they will be caught in Phase 3
4. **Testing approach:**
   - Start with unit tests and mocked external data
   - As development progresses, integration and E2E tests can be introduced
   - Push to CI when necessary for platform-specific or complex tests (the
     `azure_integration`-marked tests in `tests/azure_integration/` are the
     example of this already in the repo — see "Commands" above)
5. **Ad-hoc testing:** During development, it's fine to run ad-hoc E2E or integration tests to understand what should be tested. However, the final tests must be scripted and committed to the repo (done in Phase 3).
6. Do **not** create a pull request until Phase 3 is complete
7. Communicate blockers or scope violations immediately

### Phase 3: Polish & Audit (Autonomous)
Before signaling completion:
1. **Refactor code:**
   - Can I solve this problem simpler?
   - Do I have unnecessary code that can be removed?
   - Have I added nice-to-have features outside the user story? Remove them and suggest as future features during review.
2. **Run light security audit on code written:**
   - Linting (ruff — see "Code Style & Project Paradigm" below)
   - Check for forbidden items: plain-text secrets, tokens, server names, hardcoded resource locations (should use environment variables — see "Configuration" above)
   - Assume the entire repo is publicly readable
   - Flag any security shortcuts taken (must be justified in final review — the existing no-op `require_worker_auth` is one such already-justified shortcut, see "Security posture" above)
3. **Verify entire test suite passes:**
   - Run all unit tests locally (`pytest`; azure-marked tests only if the feature touches `adapters/azure/`)
   - Run integration and E2E tests (must be scripted and committed, not ad-hoc)
   - Verify docstring formatting doesn't break documentation build
4. **Update documentation:**
   - Update public documentation if the public interface changed
   - Update or add docstrings as needed
5. **Update changelog:**
   - Add entry under `[Unreleased]` section of `CHANGELOG.md` describing the new feature
6. **Verify feature in staging environment** (if available):
   - Run with `PARTIKKEL_STORAGE_MODE=local` against a scratch `PARTIKKEL_FORMS_LOCAL_DIR` as the local "staging" equivalent for forms-registry changes (inject a fakes-backed `JobService` into `create_app`, same as the tests, since job storage has no local mode); for job-storage/Azure-adapter changes, use Azurite or a real storage account per "Commands" above
   - Run all scripted tests including E2E
   - Staging should be empty/clean before testing
7. **Review changes for compliance:**
   - Code style and paradigm consistency (see "Code Style & Project Paradigm" below, including its noted exceptions)
   - No unintended side effects, and no violation of the layer import table in "Architecture" above
8. **Push and open the pull request to main:**
   - Push the feature branch to origin
   - Open the pull request using the Final Walkthrough Format below as its
     description (summary, diff review, decision log, alternatives
     considered, testing verification, security considerations)
   - Do not wait for a separate go-ahead to push or open the PR once steps
     1-7 pass — but this step alone is not yet the completion signal for
     Phase 3, see step 9
9. **Verify CI passes before signaling Phase 3 complete:**
   - The push in step 8 triggers `workflow_push.yml` (runs the full pytest
     suite); opening the PR triggers `workflow_pr_main.yml` (changelog/version
     gate). Watch both to completion — e.g. `gh run watch` for the push's
     run, `gh pr checks <PR#> --watch` for the PR's checks — rather than
     relying on the local `pytest` run from step 3 alone: CI is the
     authoritative signal, and it can fail for reasons a local run can't
     catch (a forgotten file, an environment difference, the version/
     changelog gate).
   - Only once every CI check on the PR is green may Phase 3 be signaled as
     complete. If a check fails, fix it, push a new commit, and re-verify —
     do not signal completion with a red or pending check.

### Phase 4: Review & Walkthrough (Collaborative)
The PR opened at the end of Phase 3 is this phase's starting point.
1. Address feedback or iterate further:
   - New commits should be added to the branch with PR comments explaining the changes
   - Do not return to Phase 2; stay in Phase 4 review mode
2. After approval: merge to main

## Feature-Scoped Constraints & Fail-Fast

During Phase 1, specific implementation constraints are agreed upon for the feature (e.g., "no new dependencies," "no changes to auth module," "must work within X timeframe"). These are boundaries, not suggestions.

**A blocker occurs when:** During implementation, you discover that a feature-scoped constraint cannot be met, or meeting it would require substantial workarounds that defy the original problem framing. (In this repo, a constraint violation also includes needing to bend the layer import table in "Architecture" above, or needing real authentication before it's in scope to add it.)

**Blocker response (do not interrupt):**
1. Stop implementation immediately
2. Document the constraint violation with specifics (what constraint, why it's violated, what was discovered)
3. Propose solutions:
   - Relax the constraint (and if so, how)
   - Reduce scope (and what would be cut)
   - Use a different technical approach (if plausible)
   - Abandon the feature
4. Prepare a wrap-up document with analysis
5. Flag that you are ready for review—do not ask for permission mid-stream

The constraint violation indicates the problem statement may need re-framing, not that the workflow needs correction.

## Code Style & Project Paradigm

### General Guidelines (Python Projects)

**Language & Dependencies:**
- Python, `pip`/`pyproject.toml` optional-dependency extras for
  environment and dependency management in this repo — not conda; see
  "Compatibility with the general workflow guide" below
- Scientific ecosystem preferred (pandas is already a dependency; xarray,
  numpy, matplotlib etc. would be reasonable additions for the future
  compute-server repo, not this one)
- New dependencies should be discussed during feature scoping

**Functional Paradigm:**
- Prefer new variable names over modifying in-place (prefer `result = func(x)` over `func(x)`)
- Functions with side effects should return nothing; if a function returns a value, it's assumed to be pure
- Prefer functions over classes; classes are acceptable but should not wrap simple logic
- Complex logic should be implemented as functions; class methods can compose these functions
- Exceptions to immutability are allowed, especially within small functions, but functions that modify input arguments are almost never acceptable
- **Named exceptions already in this codebase** (kept as-is, see "Compatibility with the general workflow guide" below for why): `SimulationJob.transition_status`/`ensure_claimed_by` (`domain/jobs.py`) intentionally mutate `self` in place as the single, auditable place status changes happen; `JobQueue.try_claim` (`ports/queue.py`) intentionally both mutates queue state and returns the claimed job id, because an atomic claim-and-report-what-you-claimed operation cannot be split into a pure read plus a separate side-effecting write without reintroducing the race it exists to prevent

**Module Organization:**
- Modules should be organized hierarchically
- Do not reference functions deep in sibling module trees
- Useful functions should be lifted to parent modules via imports (e.g., `shapely.Point` is defined in `shapely.geometry.point` but exposed at `from shapely import Point`)
- Features can be defined deep in the hierarchy but should be accessible from higher-level modules if useful to sibling subpackages
- This is secondary to the strict layer import table in "Architecture" above: lifting a name up a package's own `__init__.py` is fine, but never as a way to route around the domain/services/ports/adapters/api dependency direction

### Project-Specific Overrides

- Testing framework: pytest (already in use — `dev` extra in `pyproject.toml`)
- Linting/formatting tools: ruff (not yet added to this repo — adding it,
  and doing the first repo-wide lint pass, is itself a small feature to
  scope in Phase 1 before relying on it in Phase 3 audits)
- CI/Staging infrastructure: GitHub Actions, already present —
  `.github/workflows/action_pytest.yml` (tests), `action_changelog.yml`,
  `action_deploy.yml` and `deploy.yml` (Azure deployment, see
  `api/README.md`), `workflow_pr_main.yml`/`workflow_push.yml`. Local
  "staging" is `PARTIKKEL_STORAGE_MODE=local` against a scratch data dir;
  Azure-side staging is Azurite or a real storage account per "Commands"
  above
- Documentation system: README.md (currently well under 1000 lines) plus
  FastAPI's auto-generated OpenAPI/Swagger UI at `/docs` for the HTTP API
  itself (see "Commands" above) — no Sphinx setup yet; revisit only if
  README.md approaches the 1000-line threshold
- Areas of codebase to avoid touching casually: the layer import table in
  "Architecture" above (`domain/`, `services/`, `ports/` must stay free of
  `azure`/`pandas`/`fastapi` imports); `partikkelspredning.composition` as
  the sole composition root; `SimulationJob.transition_status` as the sole
  place `job.status` is assigned
- Additional architectural patterns or conventions: ports-and-adapters as
  described in "Architecture" above; see also the named functional-paradigm
  exceptions just above

**Note on project setup:** this project already has pytest as its testing
framework and `data/`/`tests/` conventions in place; new features grow the
existing suite rather than standing up parallel infrastructure.

## Definition of Done

A feature is complete (ready for Phase 4 review) when:
- User story acceptance criteria are met
- All tests pass:
  - New unit tests for the feature
  - All existing tests pass (integration tests for documented features must not break unless a breaking change was explicitly agreed)
  - Scripted E2E tests pass (if applicable)
- Code is refactored and simplified (unnecessary features removed)
- Security audit passes (no secrets, tokens, or server names in source)
- Public documentation is updated (if the public interface changed)
- Changelog is updated under `[Unreleased]` in `CHANGELOG.md` with the new feature
- Code style is consistent with project guidelines (including the named exceptions above)
- Documentation build succeeds without errors
- Feature verified in staging environment (if available)

## Final Walkthrough Format

When signaling completion, provide:
1. **Summary of changes** – brief description of what was implemented
2. **Diff review** – walk through code changes with context
3. **Decision log** – key decisions made and why
4. **Alternatives considered** – what else was evaluated and rejected
5. **Testing verification** – how the feature was tested
6. **Security considerations** – any security-relevant decisions

## Documentation Standards

### Public vs. Private Interface
- **Public interface:** User-facing, stable API (the `/jobs`, `/jobs/{job_id}`, `/jobs/claim`, `/jobs/{job_id}/complete`, `/jobs/{job_id}/fail`, `/form` HTTP endpoints, in both the FastAPI and Azure Functions hosting modes)
- **Private interface:** Internal implementation (domain/services/ports/adapters), can change without warning as long as the public HTTP contract and the ports Protocols' externally-relied-on guarantees (e.g. `JobQueue.try_claim`'s at-most-once guarantee) hold

Only the public interface requires public documentation. Private code can have docstrings but should be clearly separated from public docs.

### What Needs Documentation
- **HTTP API endpoints** → the FastAPI-generated OpenAPI/Swagger spec at `/docs` already serves this; keep route/schema docstrings accurate rather than hand-writing a separate spec
- **Top-level package functions** → README.md (see "Project-Specific Overrides" above)
- **Graphical UI** → N/A for this repo (the `/form`-generated page is a one-off static form, not an app UI)

### Documentation Requirements
- **Docstrings:** Mandatory for cross-module functions (the existing `domain/`/`ports/` modules already follow this); recommended for within-module functions
- **Inline code comments:** Use sparingly, only for complex logic
- **Changelog:** Always update `CHANGELOG.md` for new features (Keep a Changelog format, already in use)
- **Architecture docs:** Update this file's "Architecture" section only if public architectural principles change; internal refactors don't require updates

### Documentation Build & Sync
- Documentation must build as part of the testing procedure
- Documentation must always reflect the current source code—never mislead
- If the public interface changes, documentation must be updated

### Versioning & Releases
- This project has not yet reached its first public release (currently
  pre-1.0, see `pyproject.toml`); "Start at version 1.0.0 for the first
  public release" applies once that release happens, not retroactively
- Major version: increment only for breaking changes to the public interface
- Patch version: increment for each feature or bugfix during development (already the practice — see recent `CHANGELOG.md`/`pyproject.toml` entries)
- Changelog: add entries under `[Unreleased]` during development
- Release process: condense `[Unreleased]` into a clear summary and update version heading

Be pragmatic about breaking changes—the public interface should be small enough to allow large internal changes without breaking user contracts.

## General Principles

- **Autonomy within boundaries** – operate independently once scope is clear
- **Fail fast** – prefer abandonment over complexity creep
- **Simplicity first** – refactoring is mandatory, not optional
- **Security-conscious** – audit is built-in
- **Communication over silence** – flag issues early

## Compatibility with the general workflow guide

This file merges in the general Claude Code feature-development
workflow. Per instructions, this repo's own conventions take precedence
wherever the two disagree. The actual points of disagreement found:

1. **Package manager.** The general guide defaults to conda. This repo has
   no `environment.yml` or conda config anywhere — dependencies and extras
   are declared entirely in `pyproject.toml` and installed with
   `pip install -e ".[dev]"` (see "Commands"). Resolution: conda is
   not used for this project; treat the "Language & Dependencies" bullet
   above as overridden by `pyproject.toml`/pip.
2. **In-place mutation vs. the domain state machine.** The general guide's
   functional-paradigm section prefers pure, non-mutating functions.
   `SimulationJob.transition_status`/`ensure_claimed_by` in
   `domain/jobs.py` deliberately mutate the instance in place, on purpose,
   as the one auditable chokepoint for status changes (see "Job lifecycle"
   above and the module's own docstring). Resolution: kept as a named,
   deliberate exception rather than refactored to a
   `new_job = transition_status(job, target)` style, since the existing
   design's whole point is that there is exactly one place `job.status` is
   ever assigned.
3. **"Side effect ⇒ returns nothing" vs. `JobQueue.try_claim`.**
   `try_claim() -> Optional[str]` (`ports/queue.py`) both mutates the queue
   (removes/reserves an item) and returns the claimed id — it's neither a
   pure function nor a side-effect-only one under the general guide's rule.
   Resolution: kept as a named exception; the whole safety property this
   port exists to provide (at-most-once delivery across racing callers) is
   only achievable if the claim and the read of *what* was claimed happen
   atomically, so splitting it into a pure check plus a separate mutation
   would reintroduce the race.
4. **Linting.** No incompatibility, just a gap: the general guide's ruff
   default was adopted here since this repo had nothing already in place
   (see "Project-Specific Overrides" above) — but ruff isn't installed or
   configured yet, so don't assume Phase 3's "linting" step already has
   something to run until that's added.

Everything else in the general workflow guide (the four-phase process,
test-first implementation, changelog/versioning conventions, documentation
standards) was already compatible with, or directly matched, this repo's
existing practice and needed no reconciliation.
