import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import type { UnlistenFn } from "@tauri-apps/api/event";
import {
  createSessionId,
  listenForJobEvents,
  OperationSchema,
  RenameFormatSchema,
  sendJobControl,
  startJob,
  type JobRequest,
  type Operation,
  type RenameFormat,
  type SessionId,
  type WorkerEvent,
} from "./api/jobs";
import { HistoryPage } from "./features/history/HistoryPage";
import { OPERATIONS } from "./features/operations";
import { SettingsPage } from "./features/settings/SettingsPage";
import "./App.css";

type PreviewEvent = Extract<WorkerEvent, { type: "preview" }>;
type FileResult = Extract<WorkerEvent, { type: "file_result" }>;
type CompletedEvent = Extract<WorkerEvent, { type: "completed" }>;
type View = Operation | "history" | "settings";
type PreviewSnapshot = {
  sessionId: SessionId;
  event: PreviewEvent;
  directory: string;
  recursive: boolean;
  operation: Operation;
  options: Record<string, string | boolean>;
};
type AppState =
  | { kind: "ready"; message?: string }
  | {
      kind: "previewing";
      jobId: string;
      completed: number;
      total: number;
      path: string;
      cancelling: boolean;
    }
  | { kind: "preview-ready"; preview: PreviewSnapshot }
  | { kind: "confirming"; preview: PreviewSnapshot }
  | {
      kind: "running";
      jobId: string;
      completed: number;
      total: number;
      path: string;
      paused: boolean;
      message: string;
      files: FileResult[];
    }
  | {
      kind: "rename-decision";
      jobId: string;
      confirmationId: string;
      renamed: number;
      files: FileResult[];
    }
  | { kind: "finished"; result: CompletedEvent; files: FileResult[] }
  | { kind: "error"; message: string };

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The desktop command failed.";
}

function App() {
  const [view, setView] = useState<View>("rename");
  const parsedOperation = OperationSchema.safeParse(view);
  const operation = parsedOperation.success ? parsedOperation.data : null;
  const [directory, setDirectory] = useState("");
  const [renameFormat, setRenameFormat] = useState<RenameFormat>("artist_title");
  const [provider, setProvider] = useState<"acoustid" | "shazam">("acoustid");
  const [recognizeFirst, setRecognizeFirst] = useState(false);
  const [fetchCovers, setFetchCovers] = useState(false);
  const [recursive, setRecursive] = useState(false);
  const [state, setState] = useState<AppState>({ kind: "ready" });
  const [dialogError, setDialogError] = useState<string | null>(null);
  const currentJobId = useRef<string | null>(null);
  const requestMode = useRef<"preview" | "start" | null>(null);
  const requestSnapshot = useRef<Omit<PreviewSnapshot, "event"> | null>(null);
  const receivedPreview = useRef<PreviewEvent | null>(null);
  const confirmDialog = useRef<HTMLDialogElement>(null);
  const disposed = useRef(false);
  const unlisten = useRef<UnlistenFn | null>(null);

  const busy = ["previewing", "running", "rename-decision"].includes(state.kind);
  const canEdit = !busy && state.kind !== "confirming";

  useEffect(() => {
    disposed.current = false;
    void listenForJobEvents(
      (event) => {
        if (event.job_id !== currentJobId.current) return;
        switch (event.type) {
          case "accepted":
            return;
          case "preview":
            receivedPreview.current = event;
            return;
          case "progress":
            setState((current) => {
              if (current.kind === "previewing" && current.jobId === event.job_id) {
                return {
                  ...current,
                  completed: event.completed,
                  total: event.total,
                  path: event.path,
                };
              }
              if (current.kind !== "running" || current.jobId !== event.job_id)
                return current;
              const label =
                event.phase === "rename"
                  ? "Renaming files…"
                  : event.phase === "move"
                    ? "Moving files…"
                    : "Processing files…";
              return {
                ...current,
                completed: event.completed,
                total: event.total,
                path: event.path,
                message: label,
              };
            });
            return;
          case "file_result":
            setState((current) =>
              current.kind === "running" && current.jobId === event.job_id
                ? { ...current, files: [...current.files, event] }
                : current,
            );
            return;
          case "confirmation_required":
            setState((current) =>
              current.kind === "running" && current.jobId === event.job_id
                ? {
                    kind: "rename-decision",
                    jobId: event.job_id,
                    confirmationId: event.confirmation_id,
                    renamed: event.renamed,
                    files: current.files,
                  }
                : current,
            );
            return;
          case "warning":
            setState((current) =>
              current.kind === "running"
                ? { ...current, message: event.message }
                : current,
            );
            return;
          case "error":
            setState({ kind: "error", message: event.message });
            return;
          case "completed": {
            const mode = requestMode.current;
            currentJobId.current = null;
            requestMode.current = null;
            if (mode === "preview") {
              const preview = receivedPreview.current;
              const snapshot = requestSnapshot.current;
              receivedPreview.current = null;
              requestSnapshot.current = null;
              if (event.outcome === "success" && preview && snapshot) {
                setState({
                  kind: "preview-ready",
                  preview: { ...snapshot, event: preview },
                });
              } else if (event.outcome === "cancelled")
                setState({ kind: "ready", message: "Preview cancelled." });
              else
                setState({
                  kind: "error",
                  message: "The worker could not prepare a preview.",
                });
              return;
            }
            requestSnapshot.current = null;
            setState((current) =>
              current.kind === "error"
                ? current
                : {
                    kind: "finished",
                    result: event,
                    files:
                      current.kind === "running" || current.kind === "rename-decision"
                        ? current.files
                        : [],
                  },
            );
            return;
          }
          case "process_exit":
            currentJobId.current = null;
            requestMode.current = null;
            setState((current) =>
              current.kind === "finished" || current.kind === "error"
                ? current
                : { kind: "error", message: "The worker exited before finishing." },
            );
            return;
          case "worker_protocol_error":
            setState({
              kind: "error",
              message: "The worker returned an invalid event.",
            });
            currentJobId.current = null;
            requestMode.current = null;
        }
      },
      () =>
        setState({ kind: "error", message: "The worker returned an invalid event." }),
    )
      .then((stop) => {
        if (disposed.current) stop();
        else unlisten.current = stop;
      })
      .catch((error: unknown) =>
        setState({
          kind: "error",
          message: `Could not listen for updates: ${messageOf(error)}`,
        }),
      );
    return () => {
      disposed.current = true;
      unlisten.current?.();
    };
  }, []);

  useEffect(() => {
    if (state.kind === "confirming" && !confirmDialog.current?.open)
      confirmDialog.current?.showModal();
    else if (state.kind !== "confirming" && confirmDialog.current?.open)
      confirmDialog.current.close();
  }, [state]);

  async function chooseDirectory(): Promise<void> {
    setDialogError(null);
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: "Choose a music folder",
      });
      if (typeof selected !== "string") return;
      setDirectory(selected);
      setState({ kind: "ready" });
    } catch (error: unknown) {
      setDialogError(`Could not open the folder picker: ${messageOf(error)}`);
    }
  }

  function optionsFor(selected: Operation): Record<string, string | boolean> {
    if (selected === "rename") return { rename_format: renameFormat };
    if (selected === "recognize") return { provider };
    if (selected === "lyrics")
      return { recognize_first: recognizeFirst, fetch_covers: fetchCovers };
    return {};
  }

  async function submitJob(
    type: "preview" | "start",
    snapshot?: PreviewSnapshot,
  ): Promise<void> {
    const selected = snapshot?.operation ?? operation;
    const folder = snapshot?.directory ?? directory;
    if (!selected || !folder) return;
    const jobId = crypto.randomUUID();
    const sessionId = snapshot?.sessionId ?? createSessionId();
    const recursiveValue = snapshot?.recursive ?? recursive;
    const options = snapshot?.options ?? optionsFor(selected);
    const request: JobRequest =
      type === "preview"
        ? {
            v: 1,
            type,
            job_id: jobId,
            session_id: sessionId,
            request: {
              operation: selected,
              directory: folder,
              recursive: recursiveValue,
              options,
            },
          }
        : {
            v: 1,
            type,
            job_id: jobId,
            session_id: sessionId,
            preview_token: snapshot?.event.preview_token ?? "",
            request: {
              operation: selected,
              directory: folder,
              recursive: recursiveValue,
              options,
            },
          };
    currentJobId.current = jobId;
    requestMode.current = type;
    receivedPreview.current = null;
    requestSnapshot.current =
      type === "preview"
        ? {
            sessionId,
            directory: folder,
            recursive: recursiveValue,
            operation: selected,
            options,
          }
        : null;
    setDialogError(null);
    setState(
      type === "preview"
        ? {
            kind: "previewing",
            jobId,
            completed: 0,
            total: 0,
            path: "",
            cancelling: false,
          }
        : {
            kind: "running",
            jobId,
            completed: 0,
            total: snapshot?.event.total_files ?? 0,
            path: "",
            paused: false,
            message: `Starting ${selected}…`,
            files: [],
          },
    );
    try {
      await startJob(request);
    } catch (error: unknown) {
      currentJobId.current = null;
      requestMode.current = null;
      requestSnapshot.current = null;
      setState({
        kind: "error",
        message: `Could not start the job: ${messageOf(error)}`,
      });
    }
  }

  async function control(type: "pause" | "resume" | "cancel"): Promise<void> {
    if (state.kind !== "running") return;
    try {
      await sendJobControl({ v: 1, type, job_id: state.jobId });
      if (type !== "cancel") setState({ ...state, paused: type === "pause" });
    } catch (error: unknown) {
      setDialogError(`Could not control the job: ${messageOf(error)}`);
    }
  }

  async function cancelPreview(): Promise<void> {
    if (state.kind !== "previewing") return;
    setState({ ...state, cancelling: true });
    try {
      await sendJobControl({ v: 1, type: "cancel", job_id: state.jobId });
    } catch (error: unknown) {
      setDialogError(`Could not cancel the preview: ${messageOf(error)}`);
    }
  }

  async function answerRenameDecision(keep: boolean): Promise<void> {
    if (state.kind !== "rename-decision") return;
    try {
      await sendJobControl({
        v: 1,
        type: "confirmation_response",
        job_id: state.jobId,
        confirmation_id: state.confirmationId,
        value: keep,
      });
      setState({
        kind: "running",
        jobId: state.jobId,
        completed: 0,
        total: state.renamed,
        path: "",
        paused: false,
        message: keep ? "Keeping renamed files…" : "Restoring original filenames…",
        files: state.files,
      });
    } catch (error: unknown) {
      setState({
        kind: "error",
        message: `Could not confirm the rename: ${messageOf(error)}`,
      });
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <a className="brand" href="#main" aria-label="musren home">
          <span className="brand-mark" aria-hidden="true">
            m
          </span>
          <span>musren</span>
        </a>
        <p className="nav-label">OPERATIONS</p>
        <nav className="operation-nav" aria-label="Operations">
          {OPERATIONS.map((item) => (
            <button
              className={`nav-item${view === item.id ? " is-active" : ""}`}
              type="button"
              disabled={busy}
              aria-current={view === item.id ? "page" : undefined}
              key={item.id}
              onClick={() => {
                setView(item.id);
                setState({ kind: "ready" });
              }}
            >
              <span aria-hidden="true">·</span>
              {item.label}
            </button>
          ))}
          <p className="nav-label nav-spacer">LOCAL</p>
          {(["history", "settings"] as const).map((item) => (
            <button
              className={`nav-item${view === item ? " is-active" : ""}`}
              type="button"
              disabled={busy}
              aria-current={view === item ? "page" : undefined}
              key={item}
              onClick={() => {
                setView(item);
                setState({ kind: "ready" });
              }}
            >
              <span aria-hidden="true">·</span>
              {item === "history" ? "History" : "Settings"}
            </button>
          ))}
        </nav>
        <p className="sidebar-note">Your files and history stay on this device.</p>
      </aside>

      {view === "history" ? (
        <HistoryPage />
      ) : view === "settings" ? (
        <SettingsPage />
      ) : operation ? (
        <main className="main-content" id="main">
          <header className="topbar">
            <div>
              <p className="eyebrow">MUSIC WORKSPACE</p>
              <h1>{OPERATIONS.find((item) => item.id === operation)?.title}</h1>
            </div>
            <button
              type="button"
              className="button-secondary"
              onClick={() => void chooseDirectory()}
              disabled={!canEdit}
            >
              Choose folder
            </button>
          </header>
          <section className="workspace" aria-labelledby="folder-heading">
            <div className="folder-card">
              <div className="folder-icon" aria-hidden="true">
                ♫
              </div>
              <div className="folder-details">
                <p className="eyebrow" id="folder-heading">
                  SELECTED FOLDER
                </p>
                {directory ? (
                  <p className="folder-path" title={directory}>
                    {directory}
                  </p>
                ) : (
                  <p className="folder-empty">
                    Choose a folder to preview audio files.
                  </p>
                )}
              </div>
              {directory && (
                <button
                  type="button"
                  className="text-button"
                  onClick={() => void chooseDirectory()}
                  disabled={!canEdit}
                >
                  Change
                </button>
              )}
            </div>

            <div className="options-row">
              {operation === "rename" && (
                <div className="field-group">
                  <label htmlFor="rename-format">Naming format</label>
                  <select
                    id="rename-format"
                    value={renameFormat}
                    disabled={!canEdit}
                    onChange={(event) => {
                      const parsed = RenameFormatSchema.safeParse(
                        event.currentTarget.value,
                      );
                      if (parsed.success) {
                        setRenameFormat(parsed.data);
                        setState({ kind: "ready" });
                      }
                    }}
                  >
                    <option value="artist_title">Artist — Title</option>
                    <option value="title">Title</option>
                    <option value="track_artist_title">Track — Artist — Title</option>
                  </select>
                </div>
              )}
              {operation === "recognize" && (
                <div className="field-group">
                  <label htmlFor="provider">Recognition provider</label>
                  <select
                    id="provider"
                    value={provider}
                    disabled={!canEdit}
                    onChange={(event) => {
                      if (
                        event.currentTarget.value === "acoustid" ||
                        event.currentTarget.value === "shazam"
                      ) {
                        setProvider(event.currentTarget.value);
                        setState({ kind: "ready" });
                      }
                    }}
                  >
                    <option value="acoustid">AcoustID</option>
                    <option value="shazam">Shazam</option>
                  </select>
                </div>
              )}
              {operation === "lyrics" && (
                <div className="toggle-options">
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      checked={recognizeFirst}
                      disabled={!canEdit}
                      onChange={(event) => {
                        setRecognizeFirst(event.currentTarget.checked);
                        setState({ kind: "ready" });
                      }}
                    />
                    <span>Recognize first</span>
                  </label>
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      checked={fetchCovers}
                      disabled={!canEdit}
                      onChange={(event) => {
                        setFetchCovers(event.currentTarget.checked);
                        setState({ kind: "ready" });
                      }}
                    />
                    <span>Fetch covers</span>
                  </label>
                </div>
              )}
              {operation === "revert" ? (
                <p className="helper-text">
                  Revert scans nested folders and keeps files in place when a name
                  already exists here.
                </p>
              ) : (
                <label className="checkbox-field" htmlFor="recursive">
                  <input
                    id="recursive"
                    type="checkbox"
                    checked={recursive}
                    disabled={!canEdit}
                    onChange={(event) => {
                      setRecursive(event.currentTarget.checked);
                      setState({ kind: "ready" });
                    }}
                  />
                  <span>Include subfolders</span>
                </label>
              )}
            </div>

            {operation === "recognize" && provider === "acoustid" && (
              <p className="helper-text">
                AcoustID needs the optional pyacoustid package, fpcalc, and an API key.
                Add the key in Settings.
              </p>
            )}
            {operation === "recognize" && provider === "shazam" && (
              <p className="helper-text">
                Shazam needs the optional <code>shazam</code> extra.
              </p>
            )}
            {operation === "lyrics" && (
              <p className="helper-text">
                Lyrics lookup needs the optional lyrics dependency. Recognize-first also
                needs recognition prerequisites.
              </p>
            )}
            {dialogError && (
              <p className="inline-error" role="alert">
                {dialogError}
              </p>
            )}
            {state.kind === "error" && (
              <p className="inline-error" role="alert">
                {state.message}
              </p>
            )}
            {state.kind === "previewing" && (
              <section className="progress-section">
                <div className="preview-heading">
                  <div>
                    <p className="eyebrow">PREVIEW SCAN</p>
                    <h2>Preparing preview…</h2>
                  </div>
                  <span className="spinner" aria-hidden="true" />
                </div>
                <progress
                  value={state.completed}
                  max={Math.max(state.total, 1)}
                  aria-label="Preview scan progress"
                />
                <div className="progress-meta">
                  <span>
                    {state.completed} of {state.total} files scanned
                  </span>
                  {state.path && <span className="file-path">{state.path}</span>}
                </div>
                <button
                  className="button-secondary"
                  type="button"
                  disabled={state.cancelling}
                  onClick={() => void cancelPreview()}
                >
                  {state.cancelling ? "Cancelling…" : "Cancel scan"}
                </button>
              </section>
            )}
            {state.kind === "preview-ready" && (
              <PreviewPanel preview={state.preview.event} operation={operation} />
            )}
            {state.kind === "running" && (
              <section className="progress-section">
                <div className="preview-heading">
                  <div>
                    <p className="eyebrow">JOB IN PROGRESS</p>
                    <h2>{state.message}</h2>
                  </div>
                  <span className="status-pill">
                    {state.paused ? "Paused" : "Running"}
                  </span>
                </div>
                <progress
                  value={state.completed}
                  max={Math.max(state.total, 1)}
                  aria-label="Job progress"
                />
                <div className="progress-meta">
                  <span>
                    {state.completed} of {state.total}
                  </span>
                  {state.path && <span className="file-path">{state.path}</span>}
                </div>
                <div className="actions">
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() => void control(state.paused ? "resume" : "pause")}
                  >
                    {state.paused ? "Resume" : "Pause"}
                  </button>
                  <button
                    type="button"
                    className="button-danger"
                    onClick={() => void control("cancel")}
                  >
                    Cancel job
                  </button>
                </div>
                <p className="helper-text">
                  Cancellation takes effect at a safe step. Completed changes remain.
                </p>
              </section>
            )}
            {state.kind === "rename-decision" && (
              <section className="rename-decision">
                <p className="eyebrow">RENAME COMPLETE</p>
                <h2>Keep these changes?</h2>
                <p>
                  {state.renamed} files were renamed. Keep the new names or restore the
                  originals.
                </p>
                <div className="actions">
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() => void answerRenameDecision(false)}
                  >
                    Undo changes
                  </button>
                  <button
                    type="button"
                    className="button-primary"
                    onClick={() => void answerRenameDecision(true)}
                  >
                    Keep changes
                  </button>
                </div>
              </section>
            )}
            {state.kind === "finished" && (
              <section
                className={`result-card result-${state.result.outcome}`}
                aria-live="polite"
              >
                <p className="eyebrow">JOB RESULT</p>
                <h2>
                  {state.result.outcome === "success"
                    ? `${OPERATIONS.find((item) => item.id === operation)?.action} finished`
                    : state.result.outcome === "reverted"
                      ? "Rename changes were reverted"
                      : state.result.outcome === "partial"
                        ? "Finished with some errors"
                        : state.result.outcome === "cancelled"
                          ? state.result.retained_changes
                            ? "Cancelled; completed changes remain"
                            : "Operation cancelled"
                          : "Operation failed"}
                </h2>
                <p>
                  {state.result.outcome === "cancelled"
                    ? `${state.result.changed_files} files were changed before cancellation.`
                    : `${state.result.changed_files} changed · ${state.result.errors} errors · ${state.result.total_files} files scanned`}
                </p>
                <FileResults files={state.files} />
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => setView("history")}
                >
                  Open history
                </button>
              </section>
            )}
            <footer className="action-bar">
              <div className="action-note">
                {state.kind === "ready" && state.message
                  ? state.message
                  : state.kind === "preview-ready"
                    ? "Review the affected files before continuing."
                    : "Preview the exact plan before making changes."}
              </div>
              <div className="actions">
                <button
                  type="button"
                  className="button-secondary"
                  disabled={!directory || !canEdit}
                  onClick={() => void submitJob("preview")}
                >
                  Preview
                </button>
                {state.kind === "preview-ready" && (
                  <button
                    type="button"
                    className="button-primary"
                    disabled={state.preview.event.planned_changes === 0}
                    onClick={() =>
                      setState({ kind: "confirming", preview: state.preview })
                    }
                  >
                    {OPERATIONS.find((item) => item.id === operation)?.action}{" "}
                    {state.preview.event.planned_changes} files
                  </button>
                )}
              </div>
            </footer>
          </section>
        </main>
      ) : null}

      {state.kind === "confirming" && (
        <dialog
          ref={confirmDialog}
          className="confirmation-dialog"
          aria-labelledby="confirm-heading"
          onCancel={(event) => {
            event.preventDefault();
            setState({ kind: "preview-ready", preview: state.preview });
          }}
        >
          <p className="eyebrow">CONFIRM FILE CHANGES</p>
          <h2 id="confirm-heading">
            {OPERATIONS.find((item) => item.id === state.preview.operation)?.action}{" "}
            {state.preview.event.planned_changes} files?
          </h2>
          <p className="dialog-path">{state.preview.directory}</p>
          <p>
            This operation changes files on this device. Review the planned changes
            before continuing.
          </p>
          <ul className="sample-changes">
            {state.preview.event.files
              .filter((file) => ["rename", "move", "process"].includes(file.action))
              .slice(0, 4)
              .map((file) => (
                <li key={file.path}>
                  <span>{file.current_name}</span>
                  <span aria-hidden="true">→</span>
                  <strong>{file.target_name ?? "Processed"}</strong>
                </li>
              ))}
          </ul>
          <div className="actions dialog-actions">
            <button
              type="button"
              className="button-secondary"
              onClick={() =>
                setState({ kind: "preview-ready", preview: state.preview })
              }
            >
              Go back
            </button>
            <button
              type="button"
              className="button-primary"
              onClick={() => void submitJob("start", state.preview)}
            >
              Confirm and continue
            </button>
          </div>
        </dialog>
      )}
    </div>
  );
}

function PreviewPanel({
  preview,
  operation,
}: {
  preview: PreviewEvent;
  operation: Operation;
}) {
  return (
    <section className="preview-section" aria-labelledby="preview-heading">
      <div className="preview-heading">
        <div>
          <p className="eyebrow">REVIEW CHANGES</p>
          <h2 id="preview-heading">Preview</h2>
        </div>
        <div className="preview-counts">
          <span>
            <strong>{preview.planned_changes}</strong> planned
          </span>
          <span>
            <strong>{preview.skipped_files}</strong> skipped
          </span>
          <span>
            <strong>{preview.unchanged_files}</strong> unchanged
          </span>
        </div>
      </div>
      {preview.files.length === 0 ? (
        <p className="empty-state">No matching audio files were found.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Current item</th>
                <th scope="col">Planned result</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {preview.files.map((file) => (
                <tr key={file.path}>
                  <td title={file.path}>
                    <span className="file-name">{file.current_name}</span>
                    <span className="file-path">{file.path}</span>
                  </td>
                  <td className="target-name">
                    {file.target_name ??
                      (operation === "covers" ||
                      operation === "lyrics" ||
                      operation === "recognize"
                        ? "Metadata update"
                        : "—")}
                  </td>
                  <td>
                    <span className={`plan-badge plan-${file.action}`}>
                      {file.action}
                    </span>
                    {file.reason && <span className="plan-reason">{file.reason}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function FileResults({ files }: { files: FileResult[] }) {
  if (!files.length) return null;
  return (
    <details className="file-result-details">
      <summary>Show per-file results ({files.length})</summary>
      <ul>
        {files.map((file, index) => {
          const detail = [
            "error",
            "recognition_error",
            "lyrics_error",
            "embed_error",
            "metadata_error",
            "cover_error",
            "reason",
          ]
            .map((key) => file.result[key])
            .find((value): value is string => typeof value === "string");
          const label =
            typeof file.result.new_name === "string"
              ? `Renamed to ${file.result.new_name}`
              : typeof file.result.new_path === "string"
                ? `Moved to ${file.result.new_path}`
                : (detail ?? (file.result.skipped === true ? "Skipped" : "Processed"));
          return (
            <li key={`${file.path}-${index}`}>
              <span>{file.path}</span>
              <strong>{label}</strong>
            </li>
          );
        })}
      </ul>
    </details>
  );
}

export default App;
