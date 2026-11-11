"""Exercise preview and reversible rename through the packaged desktop worker."""

import argparse
import json
import os
import queue
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from mutagen.id3 import ID3, TIT2, TPE1


def read_events(process: subprocess.Popen, events: queue.Queue) -> None:
    """Forward worker stdout lines to the controlling thread."""
    for line in process.stdout:
        try:
            events.put(json.loads(line))
        except json.JSONDecodeError as error:
            events.put(error)
    events.put(None)


def request(
    worker: Path,
    message: dict,
    history_path: Path,
    answer_confirmation: bool = False,
) -> list[dict]:
    """Send one request and answer the worker's final confirmation if needed."""
    environment = os.environ.copy()
    environment["MUSREN_HISTORY_PATH"] = str(history_path)
    process = subprocess.Popen(
        [str(worker)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    events: queue.Queue = queue.Queue()
    threading.Thread(target=read_events, args=(process, events), daemon=True).start()
    process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    process.stdin.flush()

    received = []
    while True:
        try:
            event = events.get(timeout=30)
        except queue.Empty as error:
            process.kill()
            raise RuntimeError("Timed out waiting for the worker.") from error
        if event is None:
            break
        if isinstance(event, Exception):
            process.kill()
            raise RuntimeError(f"Worker emitted invalid JSON: {event}") from event
        received.append(event)
        if event.get("type") == "confirmation_required" and answer_confirmation:
            control = {
                "v": 1,
                "type": "confirmation_response",
                "job_id": message["job_id"],
                "confirmation_id": event["confirmation_id"],
                "value": True,
            }
            process.stdin.write(json.dumps(control) + "\n")
            process.stdin.flush()
        if event.get("type") == "completed":
            break

    process.stdin.close()
    return_code = process.wait(timeout=5)
    stderr = process.stderr.read()
    if return_code != 0:
        raise RuntimeError(f"Worker exited with {return_code}: {stderr}")
    if stderr:
        raise RuntimeError(f"Worker wrote diagnostics to stderr: {stderr}")
    return received


def smoke(worker: Path) -> None:
    """Verify Unicode preview, rename, and confirmation using a disposable MP3 tag."""
    if not worker.is_file():
        raise FileNotFoundError(f"Build the sidecar first: {worker}")

    with tempfile.TemporaryDirectory(prefix="musren desktop smoke ") as temporary:
        directory = Path(temporary) / "Música con espacios"
        directory.mkdir()
        source = directory / "original.mp3"
        source.write_bytes((b"\xff\xfb\x90\x00" + bytes(413)) * 8)
        tags = ID3()
        tags.add(TIT2(encoding=3, text="Canción de prueba"))
        tags.add(TPE1(encoding=3, text="Artista"))
        tags.save(source)

        common = {
            "v": 1,
            "session_id": str(uuid.uuid4()),
            "request": {
                "operation": "rename",
                "directory": str(directory),
                "recursive": False,
                "options": {"rename_format": "artist_title"},
            },
        }
        history_path = Path(temporary) / "history.sqlite3"
        preview = request(
            worker,
            {**common, "job_id": "desktop-smoke-preview", "type": "preview"},
            history_path,
        )
        preview_event = next(event for event in preview if event["type"] == "preview")
        if (
            preview_event["total_files"] != 1
            or preview_event["files"][0]["current_name"] != source.name
        ):
            raise AssertionError(f"Unexpected preview payload: {preview_event}")

        completed = request(
            worker,
            {
                **common,
                "job_id": "desktop-smoke-start",
                "type": "start",
                "preview_token": preview_event["preview_token"],
            },
            history_path,
            True,
        )
        final_event = next(event for event in completed if event["type"] == "completed")
        target = directory / "Artista - Canción de prueba.mp3"
        if final_event["outcome"] != "success" or not target.is_file():
            raise AssertionError(f"Rename did not complete as expected: {final_event}")

    print("Desktop worker smoke passed: preview, Unicode path, rename, confirmation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path)
    args = parser.parse_args()
    if args.worker is None:
        triple = subprocess.run(
            ["rustc", "--print", "host-tuple"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        extension = ".exe" if os.name == "nt" else ""
        args.worker = (
            Path(__file__).resolve().parents[1]
            / "desktop"
            / "src-tauri"
            / "binaries"
            / f"musren-worker-{triple}{extension}"
        )
    smoke(args.worker.resolve())
