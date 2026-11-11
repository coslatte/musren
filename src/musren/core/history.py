"""Persistent local history for desktop processing sessions."""

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal, Optional

SessionOutcome = Literal[
    "running", "previewed", "success", "partial", "cancelled", "failed", "reverted"
]
FileOutcome = Literal[
    "planned",
    "renamed",
    "unchanged",
    "skipped",
    "failed",
    "reverted",
    "processed",
    "moved",
]

_FORBIDDEN_OPTION_KEYS = (
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)


@dataclass(frozen=True)
class HistoryFile:
    """One planned and actual file change within a session."""

    ordinal: int
    path: str
    before: dict[str, Any]
    planned_after: Optional[dict[str, Any]]
    after: Optional[dict[str, Any]]
    outcome: FileOutcome
    reason: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class HistorySession:
    """A durable operation session and its per-file snapshots."""

    session_id: str
    operation: str
    directory: str
    options: dict[str, Any]
    started_at: str
    finished_at: Optional[str]
    outcome: SessionOutcome
    total_files: int
    changed_files: int
    errors: int
    files: tuple[HistoryFile, ...]
    related_session_id: Optional[str]


@dataclass(frozen=True)
class HistorySummary:
    """Session row used by the local history browser."""

    session_id: str
    operation: str
    directory: str
    started_at: str
    finished_at: Optional[str]
    outcome: SessionOutcome
    total_files: int
    changed_files: int
    errors: int
    related_session_id: Optional[str]


class HistoryStore:
    """Store session history in a private SQLite database under the user profile."""

    def __init__(self, path: Optional[Path] = None) -> None:
        configured_path = os.environ.get("MUSREN_HISTORY_PATH")
        self.path = path or (
            Path(configured_path)
            if configured_path
            else Path.home() / ".musren" / "history" / "history.sqlite3"
        )

    def start_session(
        self,
        *,
        session_id: str,
        operation: str,
        directory: str,
        options: dict[str, Any],
        expected_preview_token: Optional[str] = None,
        related_session_id: Optional[str] = None,
    ) -> None:
        """Create a session or resume its previewed record for execution."""
        _validate_public_value(options)
        now = _utc_now()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT operation, directory, options_json, outcome, preview_token "
                "FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            options_json = _json(options)
            if row is None:
                if expected_preview_token is not None:
                    raise ValueError("A saved preview is required before execution.")
                connection.execute(
                    """INSERT INTO sessions
                       (session_id, operation, directory, options_json, started_at,
                        outcome, total_files, changed_files, errors, preview_token,
                        related_session_id)
                       VALUES (?, ?, ?, ?, ?, 'running', 0, 0, 0, NULL, ?)""",
                    (
                        session_id,
                        operation,
                        directory,
                        options_json,
                        now,
                        related_session_id,
                    ),
                )
                return

            if (
                row["operation"] != operation
                or row["directory"] != directory
                or row["options_json"] != options_json
            ):
                raise ValueError("This history session ID is already in use.")
            if (
                expected_preview_token is None
                or row["outcome"] != "previewed"
                or row["preview_token"] != expected_preview_token
            ):
                raise ValueError("This history session cannot be started again.")
            connection.execute(
                "UPDATE sessions SET outcome = 'running', finished_at = NULL "
                "WHERE session_id = ?",
                (session_id,),
            )

    def save_preview(
        self,
        session_id: str,
        preview_token: str,
        files: list[dict[str, Any]],
    ) -> None:
        """Persist the complete proposed per-file plan before execution."""
        snapshots: list[HistoryFile] = []
        for ordinal, entry in enumerate(files):
            path = _required_string(entry.get("path"), "preview path")
            action = entry.get("action")
            if action not in ("rename", "move", "process", "unchanged", "skipped"):
                raise ValueError("Invalid action in operation preview.")
            before = entry.get("before", {"path": path})
            planned_after = entry.get(
                "planned_after", {"path": entry.get("target_path") or path}
            )
            if not isinstance(before, dict) or not isinstance(planned_after, dict):
                raise ValueError("Invalid file snapshots in operation preview.")
            _validate_public_value(before, "before")
            _validate_public_value(planned_after, "planned_after")
            snapshots.append(
                HistoryFile(
                    ordinal=ordinal,
                    path=path,
                    before=before,
                    planned_after=planned_after,
                    after=None,
                    outcome="planned"
                    if action in ("rename", "move", "process")
                    else action,
                    reason=entry.get("reason"),
                )
            )

        with self._connection() as connection:
            connection.execute("DELETE FROM files WHERE session_id = ?", (session_id,))
            connection.executemany(
                """INSERT INTO files
                   (session_id, ordinal, path, before_json, planned_after_json,
                    after_json, outcome, reason, error)
                   VALUES (?, ?, ?, ?, ?, NULL, ?, ?, NULL)""",
                [
                    (
                        session_id,
                        file.ordinal,
                        file.path,
                        _json(file.before),
                        _json(file.planned_after) if file.planned_after else None,
                        file.outcome,
                        file.reason,
                    )
                    for file in snapshots
                ],
            )
            connection.execute(
                "UPDATE sessions SET total_files = ?, outcome = 'previewed', "
                "finished_at = ?, preview_token = ? WHERE session_id = ?",
                (len(snapshots), _utc_now(), preview_token, session_id),
            )

    def record_result(
        self,
        *,
        session_id: str,
        path: str,
        after_path: Optional[str],
        after_snapshot: Optional[dict[str, Any]] = None,
        outcome: FileOutcome,
        reason: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Replace a planned row with the outcome observed by the audio engine."""
        after = (
            after_snapshot
            if after_snapshot is not None
            else ({"path": after_path} if after_path is not None else None)
        )
        if after is not None:
            _validate_public_value(after, "after")
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE files SET after_json = ?, outcome = ?, reason = ?, error = ?
                   WHERE session_id = ? AND path = ?""",
                (
                    _json(after) if after else None,
                    outcome,
                    reason,
                    error,
                    session_id,
                    path,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("The file result does not match the saved preview.")

    def finish_session(
        self,
        *,
        session_id: str,
        outcome: SessionOutcome,
        changed_files: int,
        errors: int,
    ) -> None:
        """Record the final outcome and exact UTC completion time."""
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE sessions SET outcome = ?, finished_at = ?,
                   changed_files = ?, errors = ? WHERE session_id = ?""",
                (outcome, _utc_now(), changed_files, errors, session_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("The history session does not exist.")

    def get_session(self, session_id: str) -> Optional[HistorySession]:
        """Return a session with its ordered per-file snapshots."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row is None:
                return None
            files = connection.execute(
                "SELECT * FROM files WHERE session_id = ? ORDER BY ordinal",
                (session_id,),
            ).fetchall()
        return HistorySession(
            session_id=row["session_id"],
            operation=row["operation"],
            directory=row["directory"],
            options=json.loads(row["options_json"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            outcome=row["outcome"],
            total_files=row["total_files"],
            changed_files=row["changed_files"],
            errors=row["errors"],
            related_session_id=row["related_session_id"],
            files=tuple(
                HistoryFile(
                    ordinal=file["ordinal"],
                    path=file["path"],
                    before=json.loads(file["before_json"]),
                    planned_after=(
                        json.loads(file["planned_after_json"])
                        if file["planned_after_json"]
                        else None
                    ),
                    after=(
                        json.loads(file["after_json"]) if file["after_json"] else None
                    ),
                    outcome=file["outcome"],
                    reason=file["reason"],
                    error=file["error"],
                )
                for file in files
            ),
        )

    def list_sessions(
        self,
        *,
        date: Optional[str] = None,
        operation: Optional[str] = None,
        outcome: Optional[str] = None,
        directory: Optional[str] = None,
    ) -> list[HistorySummary]:
        """Return newest-first session summaries filtered by local UI criteria."""
        clauses: list[str] = []
        values: list[str] = []
        if date:
            clauses.append("substr(started_at, 1, 10) = ?")
            values.append(date)
        if operation:
            clauses.append("operation = ?")
            values.append(operation)
        if outcome:
            clauses.append("outcome = ?")
            values.append(outcome)
        if directory:
            clauses.append("directory LIKE ? ESCAPE '\\'")
            values.append(
                "%"
                + directory.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
                + "%"
            )
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT session_id, operation, directory, started_at, finished_at, outcome, "
                f"total_files, changed_files, errors, related_session_id FROM sessions {where} "
                "ORDER BY started_at DESC, session_id DESC",
                values,
            ).fetchall()
        return [
            HistorySummary(
                session_id=row["session_id"],
                operation=row["operation"],
                directory=row["directory"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                outcome=row["outcome"],
                total_files=row["total_files"],
                changed_files=row["changed_files"],
                errors=row["errors"],
                related_session_id=row["related_session_id"],
            )
            for row in rows
        ]

    def clear(self) -> None:
        """Delete local session records without touching processed files."""
        with self._connection() as connection:
            connection.execute("DELETE FROM sessions")
        with self._connection() as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("VACUUM")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt":
            self.path.parent.chmod(0o700)
        connection = sqlite3.connect(self.path, timeout=10)
        if os.name != "nt":
            self.path.chmod(0o600)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """CREATE TABLE IF NOT EXISTS sessions (
                   session_id TEXT PRIMARY KEY,
                   operation TEXT NOT NULL,
                   directory TEXT NOT NULL,
                   options_json TEXT NOT NULL,
                   started_at TEXT NOT NULL,
                   finished_at TEXT,
                   outcome TEXT NOT NULL,
                   total_files INTEGER NOT NULL,
                   changed_files INTEGER NOT NULL,
                   errors INTEGER NOT NULL,
                   preview_token TEXT,
                   related_session_id TEXT
               );
               CREATE TABLE IF NOT EXISTS files (
                   session_id TEXT NOT NULL REFERENCES sessions(session_id)
                       ON DELETE CASCADE,
                   ordinal INTEGER NOT NULL,
                   path TEXT NOT NULL,
                   before_json TEXT NOT NULL,
                   planned_after_json TEXT,
                   after_json TEXT,
                   outcome TEXT NOT NULL,
                   reason TEXT,
                   error TEXT,
                   PRIMARY KEY (session_id, ordinal),
                   UNIQUE (session_id, path)
               );
               PRAGMA user_version = 2;"""
        )
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(sessions)")
        }
        if "related_session_id" not in columns:
            connection.execute(
                "ALTER TABLE sessions ADD COLUMN related_session_id TEXT"
            )
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Invalid {label}.")
    return value


def _validate_public_value(value: Any, parent: str = "options") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(forbidden in normalized for forbidden in _FORBIDDEN_OPTION_KEYS):
                raise ValueError(
                    f"Sensitive field is not allowed in history: {parent}.{key}"
                )
            _validate_public_value(item, f"{parent}.{key}")
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_public_value(item, parent)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")
