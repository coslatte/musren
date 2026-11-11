"""Run one versioned JSONL job for the Tauri sidecar supervisor."""

import json
import queue
import sqlite3
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from musren.core.credentials import KeyringCredentialStore
from musren.core.desktop_operations import (
    DesktopRequest,
    execute_operation,
    history_preview_files,
    parse_operation_request,
    prepare_operation,
)
from musren.core.history import (
    FileOutcome,
    HistorySession,
    HistoryStore,
    SessionOutcome,
)
from musren.core.jobs import undo_rename_job

PROTOCOL_VERSION = 1


def emit(job_id: str, event_type: str, **fields: Any) -> None:
    """Write one structured event to stdout."""
    event = {"v": PROTOCOL_VERSION, "job_id": job_id, "type": event_type}
    event.update(fields)
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


class JobControls:
    """Receive pause, cancel, and confirmation controls for one job."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.paused = threading.Event()
        self.cancelled = threading.Event()
        self.answers: queue.Queue = queue.Queue()

    def listen(self) -> None:
        for line in sys.stdin:
            try:
                message = json.loads(line)
                if (
                    message.get("v") != PROTOCOL_VERSION
                    or message.get("job_id") != self.job_id
                ):
                    continue
                action = message.get("type")
            except (ValueError, AttributeError):
                continue

            if action == "pause":
                self.paused.set()
            elif action == "resume":
                self.paused.clear()
            elif action == "cancel":
                self.cancelled.set()
                self.paused.clear()
            elif action == "confirmation_response":
                self.answers.put(message)

        self.cancelled.set()
        self.paused.clear()

    def checkpoint(self) -> None:
        while self.paused.is_set() and not self.cancelled.wait(0.1):
            pass
        if self.cancelled.is_set():
            raise SystemExit(130)

    def confirm(self, confirmation_id: str) -> Optional[bool]:
        while not self.cancelled.is_set():
            try:
                answer = self.answers.get(timeout=0.1)
            except queue.Empty:
                continue
            if answer.get("confirmation_id") == confirmation_id:
                value = answer.get("value")
                if isinstance(value, bool):
                    return value
        return None


def parse_request(line: str) -> tuple[Dict[str, Any], DesktopRequest]:
    """Validate the untrusted first JSONL message at the worker boundary."""
    message = json.loads(line)
    if not isinstance(message, dict) or message.get("v") != PROTOCOL_VERSION:
        raise ValueError("Unsupported or malformed worker protocol version.")

    job_id = message.get("job_id")
    if not isinstance(job_id, str) or not job_id or len(job_id) > 128:
        raise ValueError("A valid job_id is required.")
    session_id = message.get("session_id")
    if not isinstance(session_id, str):
        raise ValueError("A history session ID is required.")
    try:
        if str(uuid.UUID(session_id)) != session_id:
            raise ValueError("A canonical history session ID is required.")
    except ValueError as error:
        raise ValueError("A valid history session ID is required.") from error
    if message.get("type") not in ("preview", "start"):
        raise ValueError("Request type must be preview or start.")
    preview_token = message.get("preview_token")
    if message.get("type") == "start" and (
        not isinstance(preview_token, str)
        or len(preview_token) != 64
        or any(character not in "0123456789abcdef" for character in preview_token)
    ):
        raise ValueError("A valid preview token is required before this operation.")
    request = parse_operation_request(message.get("request"))
    return message, request


def run_request(message: Dict[str, Any], request: DesktopRequest) -> None:
    """Execute a validated operation request and stream its events."""
    job_id = message["job_id"]
    session_id = message["session_id"]
    kind = message["type"]
    controls = JobControls(job_id)
    history = HistoryStore()
    history_options = request.options
    operation = request.operation
    preview_token = message.get("preview_token")
    if kind == "preview":
        try:
            history.start_session(
                session_id=session_id,
                operation=operation,
                directory=str(request.directory),
                options=history_options,
            )
        except (OSError, RuntimeError, sqlite3.Error, ValueError) as error:
            emit(job_id, "accepted", operation=operation)
            emit(
                job_id,
                "error",
                message=f"Could not open local session history: {error}",
            )
            emit(
                job_id,
                "completed",
                outcome="failed",
                total_files=0,
                changed_files=0,
                errors=1,
            )
            return
    emit(job_id, "accepted", operation=operation)
    threading.Thread(target=controls.listen, daemon=True).start()

    def report_scan(path: str, completed: int, total: int) -> None:
        controls.checkpoint()
        emit(
            job_id,
            "progress",
            phase="scan",
            path=path,
            completed=completed,
            total=total,
        )

    try:
        preview = prepare_operation(request, on_scan=report_scan)
        if kind == "start" and preview["preview_token"] != preview_token:
            raise ValueError("Files changed after preview. Run a fresh preview.")
        if kind == "start":
            history.start_session(
                session_id=session_id,
                operation=operation,
                directory=str(request.directory),
                options=history_options,
                expected_preview_token=preview_token,
            )
    except SystemExit as error:
        if error.code != 130:
            raise
        _finish_history(
            history, session_id, outcome="cancelled", changed_files=0, errors=0
        )
        emit(
            job_id,
            "completed",
            outcome="cancelled",
            changed_files=0,
            retained_changes=False,
        )
        return
    except (OSError, RuntimeError, sqlite3.Error, ValueError) as error:
        if kind == "start":
            _finish_history(
                history, session_id, outcome="failed", changed_files=0, errors=1
            )
        elif kind == "preview":
            _finish_history(
                history, session_id, outcome="failed", changed_files=0, errors=1
            )
        emit(job_id, "error", message=f"Could not prepare this operation: {error}")
        emit(
            job_id,
            "completed",
            outcome="failed",
            total_files=0,
            changed_files=0,
            errors=1,
        )
        return

    if kind == "preview":
        try:
            controls.checkpoint()
            history.save_preview(
                session_id, preview["preview_token"], history_preview_files(preview)
            )
            _finish_history(
                history,
                session_id,
                outcome="previewed",
                changed_files=0,
                errors=0,
            )
        except SystemExit as error:
            if error.code != 130:
                raise
            _finish_history(
                history,
                session_id,
                outcome="cancelled",
                changed_files=0,
                errors=0,
            )
            emit(
                job_id,
                "completed",
                outcome="cancelled",
                changed_files=0,
                retained_changes=False,
            )
            return
        except (OSError, RuntimeError, sqlite3.Error, ValueError) as error:
            _finish_history(
                history,
                session_id,
                outcome="failed",
                changed_files=0,
                errors=1,
            )
            emit(job_id, "error", message=str(error))
            emit(
                job_id,
                "completed",
                outcome="failed",
                total_files=0,
                changed_files=0,
                errors=1,
            )
            return
        emit(
            job_id,
            "preview",
            operation=operation,
            **preview,
        )
        emit(
            job_id,
            "completed",
            outcome="success",
            total_files=preview["total_files"],
            changed_files=0,
            errors=0,
        )
        return

    changes: Dict[str, str] = {}
    file_errors = 0
    processed = 0
    actual_changes = 0
    total_files = preview["total_files"]
    needs_key = (
        operation == "recognize" and request.options.get("provider") == "acoustid"
    )
    needs_key = needs_key or (
        operation == "lyrics" and request.options.get("recognize_first", False)
    )
    credential_value: Optional[str] = None
    try:
        if needs_key:
            credential_value = KeyringCredentialStore().get_password("acoustid")
    except OSError as error:
        _finish_history(
            history, session_id, outcome="failed", changed_files=0, errors=1
        )
        emit(job_id, "error", message=str(error))
        emit(
            job_id,
            "completed",
            outcome="failed",
            total_files=total_files,
            changed_files=0,
            errors=1,
        )
        return

    def on_file(
        path: str, result: Dict[str, Any], after: Optional[dict[str, Any]]
    ) -> None:
        nonlocal file_errors, processed, actual_changes
        processed += 1
        safe_result = _redact_value(result, credential_value)
        safe_after = _redact_value(after, credential_value)
        if safe_result.get("renamed") and safe_result.get("new_name"):
            changes[str(Path(path).with_name(safe_result["new_name"]))] = path
        if (
            safe_result.get("error")
            or safe_result.get("status") is False
            or safe_result.get("outcome") == "failed"
        ):
            file_errors += 1
            outcome: FileOutcome = "failed"
        elif safe_result.get("renamed"):
            outcome = "renamed"
        elif safe_result.get("moved"):
            outcome = "moved"
        elif safe_result.get("skipped") or safe_result.get("outcome") == "skipped":
            outcome = "skipped"
        elif safe_result.get("restored"):
            outcome = "reverted"
        elif safe_result.get("outcome") == "processed":
            outcome = "processed"
        else:
            outcome = "unchanged"
        if outcome in ("renamed", "moved", "processed"):
            actual_changes += 1
        try:
            history.record_result(
                session_id=session_id,
                path=path,
                after_path=(safe_after or {}).get("path"),
                after_snapshot=safe_after,
                outcome=outcome,
                reason=str(safe_result["reason"])
                if safe_result.get("reason")
                else None,
                error=str(safe_result["error"]) if safe_result.get("error") else None,
            )
        except (OSError, sqlite3.Error, ValueError) as error:
            emit(
                job_id,
                "warning",
                message=f"Could not save one file to history: {error}",
            )
        emit(job_id, "file_result", path=path, result=safe_result)

    def report_progress(path: str, completed: int, total: int) -> None:
        controls.checkpoint()
        phase = (
            "rename"
            if operation == "rename"
            else "move"
            if operation in ("albums", "revert")
            else "process"
        )
        emit(
            job_id, "progress", phase=phase, path=path, completed=completed, total=total
        )

    try:
        changed, _operation_errors = execute_operation(
            request,
            preview,
            on_file=on_file,
            checkpoint=controls.checkpoint,
            progress=report_progress,
            acoustid_key=credential_value,
        )
    except SystemExit as error:
        if error.code != 130:
            raise
        _finish_history(
            history,
            session_id,
            outcome="cancelled",
            changed_files=actual_changes,
            errors=file_errors,
        )
        emit(
            job_id,
            "completed",
            outcome="cancelled",
            changed_files=actual_changes,
            retained_changes=actual_changes > 0,
        )
        return
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
        _finish_history(
            history,
            session_id,
            outcome="failed",
            changed_files=processed,
            errors=file_errors + 1,
        )
        emit(job_id, "error", message=_redact_text(str(error), credential_value))
        emit(
            job_id,
            "completed",
            outcome="failed",
            total_files=total_files,
            changed_files=processed,
            errors=file_errors + 1,
        )
        return

    if operation == "rename" and changes:
        confirmation_id = f"{job_id}:keep-renames"
        emit(
            job_id,
            "confirmation_required",
            confirmation_id=confirmation_id,
            message="Keep the completed rename changes?",
            renamed=len(changes),
        )
        keep_changes = controls.confirm(confirmation_id)
        if keep_changes is None:
            _finish_history(
                history,
                session_id,
                outcome="cancelled",
                changed_files=len(changes),
                errors=file_errors,
            )
            emit(
                job_id,
                "completed",
                outcome="cancelled",
                changed_files=len(changes),
                retained_changes=True,
            )
            return
        if not keep_changes:
            reverted = 0
            undo_errors = 0
            revert_session_id = str(uuid.uuid4())
            revert_token = uuid.uuid4().hex * 2
            revert_preview = [
                {
                    "path": new_path,
                    "before": {"path": new_path},
                    "planned_after": {"path": original_path},
                    "action": "move",
                }
                for new_path, original_path in changes.items()
            ]
            history.start_session(
                session_id=revert_session_id,
                operation="revert",
                directory=str(request.directory),
                options={"recursive": request.recursive, "source": "rename"},
                related_session_id=session_id,
            )
            history.save_preview(revert_session_id, revert_token, revert_preview)
            history.start_session(
                session_id=revert_session_id,
                operation="revert",
                directory=str(request.directory),
                options={"recursive": request.recursive, "source": "rename"},
                expected_preview_token=revert_token,
                related_session_id=session_id,
            )

            def on_undo(path: str, result: Dict[str, Any]) -> None:
                nonlocal reverted, undo_errors
                restored = result.get("restored") is True
                reverted += int(restored)
                original_path = changes[path]
                if result.get("error"):
                    undo_errors += 1
                try:
                    history.record_result(
                        session_id=revert_session_id,
                        path=path,
                        after_path=original_path if restored else path,
                        after_snapshot={"path": original_path if restored else path},
                        outcome="reverted" if restored else "failed",
                        error=(str(result["error"]) if result.get("error") else None),
                    )
                except (OSError, sqlite3.Error, ValueError) as error:
                    emit(
                        job_id,
                        "warning",
                        message=f"Could not save one revert to history: {error}",
                    )
                emit(job_id, "file_result", path=path, result=result)
                emit(
                    job_id,
                    "progress",
                    phase="revert",
                    path=path,
                    completed=reverted,
                    total=len(changes),
                )
                controls.checkpoint()

            cancelled = False
            try:
                undo_rename_job(changes, on_file=on_undo)
            except SystemExit as error:
                if error.code != 130:
                    raise
                cancelled = True
            except (OSError, RuntimeError, ValueError) as error:
                undo_errors += 1
                emit(
                    job_id,
                    "warning",
                    message=f"Some filenames could not be restored: {error}",
                )
            _finish_history(
                history,
                session_id,
                outcome="partial" if file_errors else "success",
                changed_files=len(changes),
                errors=file_errors,
            )
            _finish_history(
                history,
                revert_session_id,
                outcome="cancelled"
                if cancelled
                else "partial"
                if undo_errors
                else "reverted",
                changed_files=reverted,
                errors=undo_errors,
            )
            if cancelled:
                remaining = len(changes) - reverted
                emit(
                    job_id,
                    "completed",
                    outcome="cancelled",
                    changed_files=remaining,
                    retained_changes=remaining > 0,
                )
                return
            emit(
                job_id,
                "completed",
                outcome="reverted" if not undo_errors else "partial",
                total_files=len(changes),
                changed_files=reverted,
                errors=file_errors + undo_errors,
            )
            return

    outcome = "partial" if file_errors else "success"
    _finish_history(
        history,
        session_id,
        outcome=outcome,
        changed_files=changed,
        errors=file_errors,
    )
    emit(
        job_id,
        event_type="completed",
        outcome=outcome,
        total_files=total_files,
        changed_files=changed,
        errors=file_errors,
    )


def _finish_history(
    history: HistoryStore,
    session_id: str,
    *,
    outcome: SessionOutcome,
    changed_files: int,
    errors: int,
) -> None:
    try:
        history.finish_session(
            session_id=session_id,
            outcome=outcome,
            changed_files=changed_files,
            errors=errors,
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        print(
            f"Could not finish local session history: {error}",
            file=sys.stderr,
            flush=True,
        )


def run_utility(message: dict[str, Any]) -> dict[str, Any]:
    """Handle one-shot local history or credential requests without job events."""
    action = message.get("action")
    history = HistoryStore()
    if action == "history_list":
        filters = message.get("filters", {})
        if not isinstance(filters, dict):
            raise ValueError("Invalid history filters.")
        sessions = history.list_sessions(
            date=filters.get("date"),
            operation=filters.get("operation"),
            outcome=filters.get("outcome"),
            directory=filters.get("directory"),
        )
        return {"sessions": [session.__dict__ for session in sessions]}
    if action == "history_detail":
        session_id = message.get("session_id")
        if not isinstance(session_id, str):
            raise ValueError("A history session ID is required.")
        session = history.get_session(session_id)
        return {"session": _session_json(session) if session else None}
    if action == "history_clear":
        history.clear()
        return {"cleared": True}
    if action == "history_location":
        return {"history_location": str(history.path)}
    if action in ("credential_status", "credential_save", "credential_delete"):
        key = message.get("key", "acoustid")
        if key != "acoustid":
            raise ValueError("Unsupported credential name.")
        store = KeyringCredentialStore()
        if action == "credential_status":
            return {"configured": store.get_password(key) is not None}
        if action == "credential_delete":
            store.delete_password(key)
            return {"configured": False}
        value = message.get("value")
        if not isinstance(value, str) or not value or len(value) > 16384:
            raise ValueError("Enter a valid credential value.")
        store.set_password(key, value)
        return {"configured": True}
    raise ValueError("Unsupported local worker command.")


def _session_json(session: Optional[HistorySession]) -> Optional[dict[str, Any]]:
    if session is None:
        return None
    return {
        "session_id": session.session_id,
        "operation": session.operation,
        "directory": session.directory,
        "options": session.options,
        "started_at": session.started_at,
        "finished_at": session.finished_at,
        "outcome": session.outcome,
        "total_files": session.total_files,
        "changed_files": session.changed_files,
        "errors": session.errors,
        "related_session_id": session.related_session_id,
        "files": [file.__dict__ for file in session.files],
    }


def _redact_text(value: str, secret: Optional[str]) -> str:
    if secret:
        return value.replace(secret, "••••••••")
    return value


def _redact_value(value: Any, secret: Optional[str]) -> Any:
    if isinstance(value, str):
        return _redact_text(value, secret)
    if isinstance(value, dict):
        return {key: _redact_value(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, secret) for item in value]
    return value


def main() -> int:
    """Read one request from stdin and keep stdout reserved for JSONL."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    try:
        line = sys.stdin.readline()
        if not line:
            raise ValueError("A JSONL job request is required on stdin.")
        message = json.loads(line)
        if (
            isinstance(message, dict)
            and message.get("v") == PROTOCOL_VERSION
            and message.get("type") == "utility"
        ):
            result = run_utility(message)
            print(
                json.dumps({"utility_result": result}, separators=(",", ":")),
                flush=True,
            )
        else:
            message, request = parse_request(line)
            run_request(message, request)
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"Desktop worker error: {error}", file=sys.stderr, flush=True)
        return 1
    except Exception as error:
        print(
            f"Desktop worker failed: {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
