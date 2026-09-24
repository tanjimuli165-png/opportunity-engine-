from pathlib import Path
from zipfile import ZipFile
from io import BytesIO

from app.backup import create_project_backup

archive = create_project_backup(Path.cwd())
assert len(archive) > 1000
with ZipFile(BytesIO(archive)) as zip_file:
    names = set(zip_file.namelist())
    assert "requirements.txt" in names
    assert "app/main.py" in names
    assert "app/backup.py" in names
    assert "data/opportunities.db" in names
    assert not any("__pycache__" in name or ".env" in name for name in names)
source = Path("app/ui/web_interface.py").read_text()
assert "Download full project backup (.zip)" in source
print("V2.4 project backup smoke test passed")
