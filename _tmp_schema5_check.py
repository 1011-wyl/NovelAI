from pathlib import Path
import tempfile
from novel_agent.repository import SQLiteRepository, SCHEMA_VERSION

td = Path(tempfile.mkdtemp())
repo = SQLiteRepository(td / "t.db")
with repo.connection() as conn:
    vers = [r["version"] for r in conn.execute("SELECT version FROM schema_migrations")]
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(chapter_versions)")}
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
print("schema", SCHEMA_VERSION, "migrations", sorted(vers))
print("cols", sorted(cols))
needed = {
    "chapter_edit_drafts",
    "assistant_sessions",
    "assistant_messages",
    "assistant_change_sets",
}
print("tables", needed <= tables)
print(
    "mixin",
    hasattr(repo, "upsert_chapter_edit_draft"),
    hasattr(repo, "commit_chapter_revision"),
    hasattr(repo, "get_or_create_working_copy"),
)
# idempotent remigrate
SQLiteRepository(td / "t.db")
print("ok")
