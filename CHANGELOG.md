# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
