# FEATURE_PLAN.md: public_form

## User Story

**As a** system administrator  
**I want to** generate a simulation parameter form for a fixed set of parameters and deploy it as a publicly accessible static HTML page on Azure Blob Storage  
**So that** external users can fill out and submit the form without needing to call the API directly.

## Acceptance Criteria

1. A single pre-rendered form is generated for parameters: `resolution` (int), `duration` (float), `email` (text)
2. The form is uploaded to Azure Blob Storage as static HTML
3. The form is publicly readable (not requiring authentication)
4. When a user fills out and submits the form, it POSTs the parameters to `/jobs`
5. The feature works in `PARTIKKEL_STORAGE_MODE=azure` only
6. Future parameter sets can be added without architectural changes

## Feature-Scoped Constraints

- **Storage mode**: Azure only (no local fallback for this prototype)
- **Parameter set**: Single form with fixed parameters (`resolution`, `duration`, `email`) in this iteration
- **Form submission**: Uses existing `/jobs` endpoint (no new POST handler needed)
- **Dependencies**: No new external dependencies
- **Layering**: Must not violate layer import table:
  - `adapters/azure/` may use `azure.*` SDKs
  - `api/` may call services and adapters
  - `domain/`, `services/`, `ports/` remain free of Azure imports

## Implementation Notes & Architectural Decisions

### 1. Form Generation & Deployment Mechanism

The existing `/form` endpoint accepts a list of `ParameterDefinition` objects and returns HTML. For the prototype:
- Create a new function (likely in `services/`) or a simple script that:
  - Defines the parameter set (`resolution`, `duration`, `email`)
  - Calls `/form`'s underlying logic (or reuses it)
  - Uploads the HTML to Azure Blob Storage

**Decision**: Rather than add a new `/admin/deploy-form` endpoint for this iteration, implement this as:
- A utility function in `services/` that can be imported and called from tests or a management script
- Allows future features to hook into the same mechanism without duplication
- Keeps the HTTP API surface minimal for a prototype

### 2. Azure Blob Storage Integration

Create or extend `adapters/azure/` with:
- A new class (e.g., `AzureFormStore` or `AzureStaticAssetStore`) implementing a port `FormStore`/`StaticAssetStore` protocol
- Methods to upload HTML blob with correct content type, public read ACL, and optional URI
- Composition wiring in `partikkelspredning.composition` to provide this when `PARTIKKEL_STORAGE_MODE=azure`

**Port definition** (new, in `ports/`):
```python
class FormStore(Protocol):
    def upload_form_html(self, form_name: str, html_content: str) -> str:
        """Upload HTML form blob; return public URI"""
```

### 3. Form HTML Structure

The generated form must:
- Include form fields for `resolution` (input type=number), `duration` (input type=number), `email` (input type=email)
- POST to `/jobs` endpoint with JSON body: `{"parameters": {...}, "user_email": "..."}`
- Handle client-side validation (HTML5 attributes) and display submission status/errors
- Be self-contained static HTML (no external CSS/JS dependencies unless already in `/form` output)

### 4. Parameter Definition

Hardcode the parameter set for this iteration:
```python
PUBLIC_FORM_PARAMETERS = [
    ParameterDefinition(name="resolution", type="integer", description="Grid resolution"),
    ParameterDefinition(name="duration", type="float", description="Simulation duration (seconds)"),
    ParameterDefinition(name="email", type="text", description="Notification email"),
]
```

Store this in `domain/parameters.py` or a new `domain/public_forms.py` module.

### 5. Testing Strategy

- **Unit tests**: Mock `FormStore` and test form generation logic
- **Integration tests** (marked `azure_integration`): Use Azurite or a real storage account
  - Upload a form
  - Verify blob is readable and contains expected HTML
  - Verify generated form submits correctly (can use a test HTTP client)
- **E2E test** (optional for prototype): Full flow from deployment to form submission → job created

### 6. Future Extensibility

Design for addition of more parameter sets:
- `PUBLIC_FORM_PARAMETERS` is a single list; a future feature could refactor this to a registry of named form configs
- `upload_form_html` method can accept metadata (form name, version, etc.) without breaking the prototype
- Form name/URI strategy TBD in future feature scoping

## Deployment & Configuration

- No new environment variables needed for the prototype (reuse `AZURE_STORAGE_CONNECTION_STRING`)
- Form upload can be triggered manually (via a CLI tool or test) or during app initialization (if appropriate)
- **Note**: Exact URL/URI of the form in Blob Storage is not critical for this prototype; TBD in Phase 4 review

## Security Considerations

- Form is public read (no authentication required) — intentional for this use case
- Form submission POSTs to `/jobs`, which currently has no authentication (`require_worker_auth` is a no-op) — existing constraint, not introduced by this feature
- HTML is static; no server-side code injection risk
- Email field validates format server-side in `/jobs` handler

## Blocked or Deferred

- Multi-form support (deferred to future feature)
- Admin endpoint to deploy/manage forms (deferred; manual/scripted for now)
- Public listing of available forms (deferred)
- Form versioning/history (deferred)

---

**Ready for Phase 2 (Implementation) once approved.**
