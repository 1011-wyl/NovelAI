from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novel_agent.repository import SQLiteRepository


class AnalyticsStoreTransactionTests(unittest.TestCase):
    def test_record_writing_activity_commits_with_external_connection(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = SQLiteRepository(Path(folder) / "commit.db")
            with repository.transaction() as conn:
                conn.execute(
                    """INSERT INTO projects
                    (id,title,status,request_json,brief_json,confirmed,current_chapter,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        "novel_tx",
                        "事务书",
                        "ACTIVE",
                        "{}",
                        "{}",
                        1,
                        0,
                        "2026-09-28T00:00:00Z",
                        "2026-09-28T00:00:00Z",
                    ),
                )
                repository.record_writing_activity(
                    project_id="novel_tx",
                    chapter_id="c_tx",
                    chapter_title="第一章",
                    source="user",
                    operation="edit",
                    old_word_count=10,
                    new_word_count=25,
                    created_at="2026-09-28T01:00:00Z",
                    conn=conn,
                )
            with repository.connection() as conn:
                project_count = conn.execute(
                    "SELECT COUNT(*) AS c FROM projects WHERE id='novel_tx'"
                ).fetchone()["c"]
                event_count = conn.execute(
                    """SELECT COUNT(*) AS c FROM writing_activity_events
                       WHERE project_id='novel_tx' AND word_delta=15"""
                ).fetchone()["c"]
            self.assertEqual(project_count, 1)
            self.assertEqual(event_count, 1)

    def test_record_writing_activity_rolls_back_with_external_connection(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = SQLiteRepository(Path(folder) / "rollback.db")
            try:
                with repository.transaction() as conn:
                    conn.execute(
                        """INSERT INTO projects
                        (id,title,status,request_json,brief_json,confirmed,current_chapter,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            "novel_rb",
                            "回滚书",
                            "ACTIVE",
                            "{}",
                            "{}",
                            1,
                            0,
                            "2026-09-28T00:00:00Z",
                            "2026-09-28T00:00:00Z",
                        ),
                    )
                    repository.record_writing_activity(
                        project_id="novel_rb",
                        chapter_id="c_rb",
                        chapter_title="第一章",
                        source="agent",
                        operation="create",
                        old_word_count=0,
                        new_word_count=40,
                        created_at="2026-09-28T02:00:00Z",
                        conn=conn,
                    )
                    raise RuntimeError("force rollback")
            except RuntimeError:
                pass
            with repository.connection() as conn:
                project_count = conn.execute(
                    "SELECT COUNT(*) AS c FROM projects WHERE id='novel_rb'"
                ).fetchone()["c"]
                event_count = conn.execute(
                    """SELECT COUNT(*) AS c FROM writing_activity_events
                       WHERE project_id='novel_rb'"""
                ).fetchone()["c"]
            self.assertEqual(project_count, 0)
            self.assertEqual(event_count, 0)


if __name__ == "__main__":
    unittest.main()
