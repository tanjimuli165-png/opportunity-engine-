from pathlib import Path
from tempfile import TemporaryDirectory

from app.database.db import ReportStore

with TemporaryDirectory() as directory:
    store = ReportStore(Path(directory) / "sessions.db")
    ok, _ = store.register_user("alice", "correct-horse-123")
    assert ok
    user = store.authenticate("alice", "correct-horse-123")
    token = store.create_session(user["user_id"], days=30)
    restored = store.authenticate_session(token)
    assert restored and restored["username"] == "alice"
    store.revoke_session(token)
    assert store.authenticate_session(token) is None

source = Path("app/ui/web_interface.py").read_text()
assert "localStorage" in source
assert "create_session" in source
assert "authenticate_session" in source
assert "revoke_session" in source
assert "removeItem" in source
print("V2.2 persistent session smoke test passed")
