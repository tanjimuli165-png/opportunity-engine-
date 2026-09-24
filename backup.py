from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


EXCLUDED_PARTS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".venv", "venv"}
INCLUDED_ROOT_FILES = {"requirements.txt", "README.md"}


def _is_allowed(path: Path, base: Path) -> bool:
    relative_parts = set(path.relative_to(base).parts)
    return not relative_parts.intersection(EXCLUDED_PARTS) and path.is_file()


def create_project_backup(base_dir: Path) -> bytes:
    """Return a ZIP containing project source, dependencies, tests, and the local DB."""
    base_dir = Path(base_dir).resolve()
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path in sorted((base_dir / "app").rglob("*")) if (base_dir / "app").exists() else []:
            if _is_allowed(path, base_dir):
                archive.write(path, path.relative_to(base_dir).as_posix())
        for path in sorted(base_dir.iterdir()):
            if path.is_file() and (path.name in INCLUDED_ROOT_FILES or (path.name.startswith("v") and path.name.endswith("_smoke_test.py"))):
                archive.write(path, path.relative_to(base_dir).as_posix())
        database = base_dir / "data" / "opportunities.db"
        if database.exists():
            archive.write(database, database.relative_to(base_dir).as_posix())
    return buffer.getvalue()


__all__ = ["create_project_backup"]
