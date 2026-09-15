# FEATURE_PLAN.md: multiple_forms

## User Story

As an operator, I want to discover and access pre-configured simulation forms from a landing page, so that I can run standard experiments without needing to know URLs or parameter sets in advance.

## Acceptance Criteria

1. **Form definitions in JSON:** Forms are defined in a single `api/forms.json` file, each with a name, description, and full parameter list (compatible with existing `ParameterDefinition` structure)
2. **Pre-rendered forms at startup:** On app startup (both Azure Functions and local dev), all forms in `api/forms.json` are pre-rendered to static HTML files and stored via a `FormsStore` adapter (blob storage in Azure, local disk in development)
3. **Index landing page:** `GET /` endpoint returns an HTML page listing all available forms with clickable links to the pre-rendered form pages
4. **Forms metadata endpoint:** `GET /forms` endpoint returns a JSON object with form metadata (id, name, description, parameter definitions) for programmatic access
5. **Static file serving:** Pre-rendered forms are served as static HTML assets from blob storage (Azure) or disk (development), not generated on-demand
6. **No local FastAPI deployment:** The `uvicorn` development/local deployment mode is removed; Azure Functions is the only deployment target going forward
7. **No local adapters:** The `adapters/local/` directory is removed entirely; only Azure adapters remain

## Feature-Scoped Constraints

- **No new dependencies:** Reuse existing libraries (pydantic, fastapi, azure SDKs as applicable)
- **Ports/adapters separation maintained:** Even though local mode is removed, the ports/adapters abstraction is preserved for future cloud vendor flexibility (not Azure-specific business logic)
- **No authentication for form discovery:** The index page and form pages are public; no auth required to discover or submit forms (existing `require_worker_auth` no-op stays for compute server endpoints)
- **No admin endpoints yet:** Forms are source-code-only; no CRUD endpoints for adding/updating forms dynamically

## Implementation Notes

### Architecture & Files

**New files:**
- `api/forms.json` – Form definitions (name, description, parameters list)
- `src/partikkelspredning/services/form_registry.py` – Service to load forms.json and prepare form definitions (business logic, no Azure/FastAPI/pandas imports)
- `src/partikkelspredning/ports/forms_store.py` – `FormsStore` protocol (port) defining interface for storing/retrieving pre-rendered forms
- `src/partikkelspredning/adapters/azure/forms_store.py` – Azure blob storage implementation of FormsStore
- `src/partikkelspredning/api/routes_index.py` – `GET /` and `GET /forms` endpoints

**Modified files:**
- `src/partikkelspredning/main.py` – Remove or deprecate (local uvicorn is no longer an entry point)
- `src/partikkelspredning/api/app.py` – Remove dynamic `/form` endpoint and router; add index router with GET / and GET /forms; trigger form pre-rendering on startup
- `src/partikkelspredning/composition.py` – Remove local adapter composition logic; instantiate Azure FormsStore
- `api/function_app.py` – Trigger form pre-rendering on startup; ensure FormsStore is initialized
- `src/partikkelspredning/config.py` – Add configuration for forms.json path (default `api/forms.json` relative to package)

**Removed/deprecated:**
- `src/partikkelspredning/adapters/local/` – Removed entirely
- `src/partikkelspredning/services/form_service.py` – Dynamic form generation (replace with pre-rendered approach); tests updated accordingly
- `src/partikkelspredning/api/routes_form.py` – Dynamic `/form` endpoint removed
- `uvicorn` from dependencies

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
   - Write tests for `form_registry` service (loading JSON, validating structure, creating ParameterDefinition objects)
   - Implement form registry to parse `api/forms.json` into Form objects with ParameterDefinition lists
   - Create `FormsStore` protocol in `ports/forms_store.py` (interface for storing/retrieving pre-rendered HTML)
   - Implement `AzureFormsStore` adapter (uses blob storage to store/serve pre-rendered forms)
   - Write tests for form pre-rendering utility (generates HTML from Form definitions)
   - Implement form pre-rendering in startup sequence (app initialization calls pre-rendering)
   - Write tests for index routes (`GET /` returns HTML, `GET /forms` returns JSON metadata)
   - Implement `GET /` and `GET /forms` endpoints
   - Remove local adapters, uvicorn entry point, and dynamic form generation (`routes_form.py`, `form_service.py`)
   - Update composition root to use Azure-only setup

2. **Phase 3 (Polish):**
   - Verify all existing tests pass (form generation tests may need removal/updating)
   - Run security audit (no secrets in forms.json or pre-rendered HTML)
   - Update README and api/README.md to reflect Azure-only deployment and new endpoints
   - Update CHANGELOG.md
   - Verify index page and forms render correctly in staging (Azurite or real blob storage)
   - Test startup pre-rendering behavior (verify forms are rendered on first request)

## Key Decisions

1. **Pre-rendering at app startup (not deployment time):** Forms are pre-rendered when the app initializes, stored in blob storage via FormsStore adapter. This keeps runtime behavior testable and consistent across development/production.
2. **FormsStore port/adapter pattern:** Pre-rendered forms are stored/retrieved via a protocol, allowing different implementations (Azure blob storage in production, local disk in testing). Maintains architectural flexibility.
3. **Single forms.json file:** Simpler to manage than a directory; can grow to a forms/ directory later if needed
4. **JSON-based form definitions:** Decoupled from Python code; non-developers can add forms without code changes
5. **Removed local adapters and FastAPI:** Simplifies the codebase; Azure Functions is the only deployment target. Reduces test surface and removes unused code.
6. **GET / for HTML index, GET /forms for JSON metadata:** Provides both human-discoverable (HTML with links) and machine-readable (JSON) interfaces

## Alternatives Considered

1. **Dynamic form generation at runtime:** Would require validating forms.json on each request; rejected in favor of pre-rendering for performance
2. **Forms as Python datafiles:** Rejected because JSON is more portable and allows non-devs to manage forms
3. **Keep local mode alongside Azure:** Rejected because no users rely on it, and it adds maintenance burden

## Design Decisions to Finalize During Phase 2

- **Blob storage path structure:** Forms will be stored as `/forms/{form_id}.html` in blob storage; index page links point to these paths
- **Index page caching:** Index page (HTML list of forms) is pre-rendered once at startup, then cached. Changes to forms.json require app restart.
- **Missing forms.json handling:** If forms.json is not found on startup, app logs a warning and continues with an empty forms list (graceful degradation)
- **Concurrent startup:** If app starts in multiple instances simultaneously, all will try to pre-render; blob storage PUT operations are idempotent, so this is safe

(No architectural blockers identified.)
