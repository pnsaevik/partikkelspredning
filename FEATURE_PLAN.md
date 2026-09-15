# FEATURE_PLAN.md: multiple_forms

## User Story

As an operator, I want to discover and access pre-configured simulation forms from a landing page, so that I can run standard experiments without needing to know URLs or parameter sets in advance.

## Acceptance Criteria

1. **Form definitions in JSON:** Forms are defined in a single `src/partikkelspredning/forms/definitions.json` file, each with a name, description, and full parameter list (compatible with existing `ParameterDefinition` structure)
2. **Pre-rendered forms at startup:** On app startup (both Azure Functions and local dev), all forms in `src/partikkelspredning/forms/definitions.json` are pre-rendered to static HTML files and stored via a `FormsStore` adapter (blob storage in Azure, local disk in development)
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
- `src/partikkelspredning/forms/definitions.json` – Form definitions (name, description, parameters list)
- `src/partikkelspredning/services/form_registry.py` – Service to load definitions.json and prepare form definitions (business logic, no Azure/FastAPI/pandas imports)
- `src/partikkelspredning/ports/forms_store.py` – `FormsStore` protocol (port) defining interface for storing/retrieving pre-rendered forms
- `src/partikkelspredning/adapters/azure/forms_store.py` – Azure blob storage implementation of FormsStore
- `src/partikkelspredning/adapters/local/forms_store.py` – Local filesystem implementation of FormsStore (for development/testing)
- `src/partikkelspredning/services/form_renderer.py` – Pre-rendering utility (generates HTML from Form definitions, calls FormsStore to persist)
- `src/partikkelspredning/api/routes_index.py` – `GET /` and `GET /forms` endpoints

**Modified files:**
- `src/partikkelspredning/main.py` – Remove or deprecate (local uvicorn is no longer an entry point)
- `src/partikkelspredning/api/app.py` – Remove dynamic `/form` endpoint and router; add index router with GET / and GET /forms; trigger form pre-rendering on startup
- `src/partikkelspredning/composition.py` – Remove local adapter composition logic; instantiate Azure FormsStore
- `api/function_app.py` – Trigger form pre-rendering on startup; ensure FormsStore is initialized
- `src/partikkelspredning/config.py` – Add configuration for forms.json path (default `api/forms.json` relative to package)

**Removed/deprecated:**
- `src/partikkelspredning/adapters/local/` – Entire directory removed (CSV, queue, result store adapters no longer needed; replaced with Azure-only + local FormsStore for testing)
- `src/partikkelspredning/services/form_service.py` – Dynamic form generation replaced by pre-rendering
- `src/partikkelspredning/api/routes_form.py` – Dynamic `/form` endpoint removed
- `tests/test_form_service.py` and `tests/test_public_form_service.py` – Tests for removed functionality
- `src/partikkelspredning/main.py` – uvicorn entry point (local deployment removed)
- `uvicorn` from dependencies

### JSON Schema (src/partikkelspredning/forms/definitions.json)

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

## Design Decisions (Finalized)

### Data and Configuration
- **forms.json location:** `src/partikkelspredning/forms/definitions.json` (packaged with source code, loaded via package resources at runtime)
- **Configuration:** Add to `src/partikkelspredning/config.py`:
  - `FORMS_DEFINITIONS_PATH` (default: `forms/definitions.json` relative to package)
  - `FORMS_BLOB_CONTAINER` (for Azure, the container name storing pre-rendered forms)
  - `FORMS_LOCAL_DIR` (for local development, directory for storing pre-rendered forms)

### Static File Serving
- **Blob storage path structure:** Forms stored as `forms/{form_id}.html` in blob storage container
- **Serving mechanism:** Index page and `GET /forms` endpoint include full blob storage URLs; clients access forms directly from blob storage (no proxying through API)
- **URL format:** `https://{storage_account}.blob.core.windows.net/{container_name}/forms/{form_id}.html` (Azure), or local file path (development)

### Startup and Error Handling
- **Startup pre-rendering:** Forms are pre-rendered to storage on app initialization (before accepting requests)
- **Startup failure behavior:** Fast-fail—if pre-rendering fails, the app raises an exception and fails to start. This ensures forms are always available when the app is running.
- **Index page caching:** Index page (HTML list) is pre-rendered once at startup and cached in memory. Changes to `forms.json` require app restart.
- **Concurrent startup:** If multiple instances start simultaneously, all attempt pre-rendering; blob storage operations are idempotent (safe).

### Storage Abstraction
- **FormsStore implementations:**
  - `AzureFormsStore`: Stores/retrieves pre-rendered forms from Azure blob storage
  - `LocalFormsStore`: Stores/retrieves pre-rendered forms from local filesystem (for development/testing)
- **Selection at runtime:** `composition.py` instantiates the appropriate implementation based on configuration
- **Abstraction rationale:** Maintains flexibility for future cloud vendor changes; enables local development without Azurite

### Removed Functionality
- **Removed code:** `src/partikkelspredning/services/form_service.py` (dynamic form generation), `src/partikkelspredning/api/routes_form.py` (dynamic `/form` endpoint)
- **Removed tests:** `tests/test_form_service.py`, `tests/test_public_form_service.py` (these test functionality that is being replaced)
- **Removed adapters:** `src/partikkelspredning/adapters/local/` (entire local adapter directory)
- **Removed entry points:** `src/partikkelspredning/main.py` (uvicorn entry point deprecated)
- **Removed dependencies:** `uvicorn` from `pyproject.toml`

(No architectural blockers identified.)
