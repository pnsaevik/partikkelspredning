"""Local filesystem implementation of `FormStore`.

Writes pre-rendered form HTML to plain files on disk - used for local
development and the default test suite's forms-registry coverage (see
`partikkelspredning.composition.build_forms_store`), never for the
production public form deploy path (`build_form_store`, Azure-only,
unchanged). No locking is needed here, unlike the old CSV adapters: each
call is a single, independent file write, not a concurrent
read-modify-write.
"""
from __future__ import annotations

from pathlib import Path


class LocalFormStore:
    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)

    def upload_form_html(self, form_name: str, html_content: str) -> str:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{form_name}.html"
        path.write_text(html_content, encoding="utf-8")
        return str(path)
