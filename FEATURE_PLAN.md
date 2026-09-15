# FEATURE_PLAN.md: multiple_forms

## User Story

As an operator, I want to discover and access pre-configured simulation forms from a landing page, so that I can run standard experiments without needing to know URLs or parameter sets in advance.

## Acceptance Criteria

1. **Form definitions in JSON:** Forms are defined in a single `api/forms.json` file, each with a name, description, and full parameter list (compatible with existing `ParameterDefinition` structure)
2. **Pre-rendered forms at deployment:** During Azure deployment, all forms in `api/forms.json` are pre-rendered to static HTML files and stored in blob storage under a predictable path (e.g., `/forms/`)
3. **Index landing page:** A simple `GET /` endpoint returns an HTML page listing all available forms with clickable links to the pre-rendered form pages
4. **Static file serving:** Pre-rendered forms are served as static HTML assets, not generated on-demand
5. **No local FastAPI deployment:** The `uvicorn` development/local deployment mode is removed; Azure Functions is the only deployment target going forward

## Feature-Scoped Constraints

- **No new dependencies:** Reuse existing libraries (pydantic, fastapi, azure SDKs as applicable)
- **Ports/adapters separation maintained:** Even though local mode is removed, the ports/adapters abstraction is preserved for future cloud vendor flexibility (not Azure-specific business logic)
- **No authentication for form discovery:** The index page and form pages are public; no auth required to discover or submit forms (existing `require_worker_auth` no-op stays for compute server endpoints)
- **No admin endpoints yet:** Forms are source-code-only; no CRUD endpoints for adding/updating forms dynamically

## Implementation Notes

### Architecture & Files

**New files:**
- `api/forms.json` – Form definitions (name, description, parameters list)
- `src/partikkelspredning/services/form_registry.py` – Service to load and manage form definitions (business logic, no Azure/FastAPI imports)
- `src/partikkelspredning/api/routes_index.py` – GET `/` endpoint returning the index page
- Deployment step (in `api/README.md` or GH Actions) to pre-render forms and upload to blob storage

**Modified files:**
- `src/partikkelspredning/main.py` – Remove or deprecate (local uvicorn is no longer an entry point)
- `src/partikkelspredning/api/app.py` – Remove form router import (pre-rendered forms replace dynamic `/form` endpoint); add index router
- `src/partikkelspredning/composition.py` – Remove local adapter composition logic; keep Azure-only (or make it clear this is for Azure only)
- `api/function_app.py` – Ensure it serves pre-rendered forms as static content (or ensure blob storage is accessible)
- `.github/workflows/` – Update deployment workflow to include pre-rendering step
- `api/README.md` – Update to reflect Azure-only deployment

**Removed/deprecated:**
- `src/partikkelspredning/adapters/local/` – Can be removed entirely once local deployment is confirmed gone
- `uvicorn` from dependencies (if no other use case exists)

### JSON Schema (api/forms.json)

```json
{
  "forms": [
    {
      "id": "standard_resolution",
      "name": "Standard Resolution Simulation",
      "description": "A baseline 1km resolution simulation over 30 days",
      "parameters": [
        {
          "name": "resolution",
          "type": "integer",
          "description": "Grid resolution in meters"
        },
        {
          "name": "duration",
          "type": "integer",
          "description": "Simulation duration in days"
        }
      ]
    }
  ]
}
```

### Implementation Approach

1. **Phase 2 (Implementation):**
   - Write tests for `form_registry` service (loading JSON, validating structure)
   - Implement form registry to parse `api/forms.json` (pure function, no framework deps)
   - Write tests for index route (mocked form registry)
   - Implement GET `/` route returning HTML with links to pre-rendered forms
   - Create pre-rendering utility (generates HTML files from form definitions)
   - Update deployment workflow to call pre-renderer and upload to blob storage
   - Remove local uvicorn entry point and adapters

2. **Phase 3 (Polish):**
   - Verify all existing tests still pass (form generation tests may need updating)
   - Run security audit (no secrets in forms.json or pre-rendered HTML)
   - Update README and api/README.md to reflect Azure-only deployment
   - Update CHANGELOG.md
   - Verify index page and forms render correctly in staging (Azurite or real blob storage)

## Key Decisions

1. **Pre-rendering at deployment (not runtime):** Keeps the form list static and fast; changes to forms require a new deployment
2. **Single forms.json file:** Simpler to manage than a directory; can grow to a forms/ directory later if needed
3. **JSON-based form definitions:** Decoupled from Python code; non-developers can add forms without code changes
4. **Removed local FastAPI:** Simplifies the codebase and CI/CD; Azure Functions is the canonical deployment

## Alternatives Considered

1. **Dynamic form generation at runtime:** Would require validating forms.json on each request; rejected in favor of pre-rendering for performance
2. **Forms as Python datafiles:** Rejected because JSON is more portable and allows non-devs to manage forms
3. **Keep local mode alongside Azure:** Rejected because no users rely on it, and it adds maintenance burden

## Blockers / Open Questions

- How should pre-rendered forms be stored in blob storage? (e.g., a container named `forms`, paths like `/forms/{form_id}.html`)
- Should the form index page be pre-rendered once at deployment, or generated dynamically at request time?
- Do we need a fallback if blob storage is unavailable, or assume it always is during request handling?

(These will be resolved during Phase 2 scoping; no architectural blockers identified.)
