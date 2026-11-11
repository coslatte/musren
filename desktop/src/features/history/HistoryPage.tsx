import { useEffect, useState } from "react";
import {
  clearHistory,
  getHistory,
  listHistory,
  type HistoryDetail,
  type HistorySummary,
  type SessionId,
} from "../../api/jobs";
import { OPERATIONS } from "../operations";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The desktop command failed.";
}

function displayTime(value: string): string {
  const date = new Date(value);
  return `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium", timeZoneName: "short" }).format(date)} · ${date.toISOString()}`;
}

function localDate(value: string): string {
  const date = new Date(value);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function HistoryPage() {
  const [sessions, setSessions] = useState<HistorySummary[]>([]);
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [filters, setFilters] = useState({
    date: "",
    operation: "",
    outcome: "",
    directory: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const result = await listHistory({
        operation: filters.operation,
        outcome: filters.outcome,
        directory: filters.directory,
      });
      setSessions(
        result.filter(
          (session) => !filters.date || localDate(session.started_at) === filters.date,
        ),
      );
    } catch (failure: unknown) {
      setError(messageOf(failure));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [filters.date, filters.operation, filters.outcome, filters.directory]);

  async function openSession(sessionId: SessionId): Promise<void> {
    try {
      setDetail(await getHistory(sessionId));
      setError(null);
    } catch (failure: unknown) {
      setError(messageOf(failure));
    }
  }

  async function clearAll(): Promise<void> {
    if (
      !window.confirm(
        "Clear all local session history? Processed audio files will not change.",
      )
    )
      return;
    try {
      await clearHistory();
      setDetail(null);
      await refresh();
    } catch (failure: unknown) {
      setError(messageOf(failure));
    }
  }

  return (
    <main className="main-content" id="main">
      <header className="topbar">
        <div>
          <p className="eyebrow">LOCAL RECORDS</p>
          <h1>History</h1>
        </div>
        <button
          className="button-secondary"
          type="button"
          onClick={() => void clearAll()}
        >
          Clear history
        </button>
      </header>
      <section className="workspace">
        <p className="helper-text">
          Sessions are stored locally. Timestamps show your local timezone and the exact
          UTC instant.
        </p>
        <div className="history-filters">
          <label>
            Date
            <input
              type="date"
              value={filters.date}
              onChange={(event) =>
                setFilters({ ...filters, date: event.currentTarget.value })
              }
            />
          </label>
          <label>
            Operation
            <select
              value={filters.operation}
              onChange={(event) =>
                setFilters({ ...filters, operation: event.currentTarget.value })
              }
            >
              <option value="">All operations</option>
              {OPERATIONS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Outcome
            <select
              value={filters.outcome}
              onChange={(event) =>
                setFilters({ ...filters, outcome: event.currentTarget.value })
              }
            >
              <option value="">All outcomes</option>
              {[
                "success",
                "partial",
                "cancelled",
                "failed",
                "reverted",
                "previewed",
              ].map((outcome) => (
                <option key={outcome}>{outcome}</option>
              ))}
            </select>
          </label>
          <label>
            Folder
            <input
              type="search"
              value={filters.directory}
              onChange={(event) =>
                setFilters({ ...filters, directory: event.currentTarget.value })
              }
              placeholder="Search folder path"
            />
          </label>
        </div>
        {error && (
          <p role="alert" className="inline-error">
            {error}
          </p>
        )}
        <div className="history-layout">
          <div className="history-list" aria-busy={loading}>
            {sessions.length === 0 ? (
              <p className="empty-state">
                {loading ? "Loading sessions…" : "No sessions match these filters."}
              </p>
            ) : (
              sessions.map((session) => (
                <button
                  type="button"
                  className={`history-row${detail?.session_id === session.session_id ? " is-selected" : ""}`}
                  key={session.session_id}
                  onClick={() => void openSession(session.session_id)}
                >
                  <strong>{displayTime(session.started_at)}</strong>
                  <span>
                    {session.operation} · {session.outcome}
                  </span>
                  <span className="file-path">{session.directory}</span>
                  <small>
                    {session.changed_files} changed · {session.errors} errors ·{" "}
                    {session.total_files} files
                  </small>
                </button>
              ))
            )}
          </div>
          {detail && (
            <section className="history-detail">
              <div className="preview-heading">
                <div>
                  <p className="eyebrow">SESSION DETAILS</p>
                  <h2>
                    {detail.operation} · {detail.outcome}
                  </h2>
                </div>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => setDetail(null)}
                >
                  Close
                </button>
              </div>
              <p>
                <strong>Started:</strong> {displayTime(detail.started_at)}
              </p>
              {detail.finished_at && (
                <p>
                  <strong>Finished:</strong> {displayTime(detail.finished_at)}
                </p>
              )}
              <p className="file-path">{detail.directory}</p>
              {detail.related_session_id && (
                <p>
                  Related session:{" "}
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => {
                      if (detail.related_session_id)
                        void openSession(detail.related_session_id);
                    }}
                  >
                    {detail.related_session_id}
                  </button>
                </p>
              )}
              <h3>Options used</h3>
              <pre>{JSON.stringify(detail.options, null, 2)}</pre>
              <h3>File changes ({detail.files.length})</h3>
              <div className="history-file-list">
                {detail.files.map((file) => (
                  <article key={`${file.ordinal}-${file.path}`}>
                    <strong>{file.outcome}</strong>
                    <span className="file-path">{file.path}</span>
                    <dl>
                      <dt>Before</dt>
                      <dd>
                        <pre>{JSON.stringify(file.before, null, 2)}</pre>
                      </dd>
                      <dt>Planned</dt>
                      <dd>
                        <pre>{JSON.stringify(file.planned_after, null, 2)}</pre>
                      </dd>
                      <dt>Actual</dt>
                      <dd>
                        <pre>{JSON.stringify(file.after, null, 2)}</pre>
                      </dd>
                    </dl>
                    {file.reason && <p>{file.reason}</p>}
                    {file.error && <p className="inline-error">{file.error}</p>}
                  </article>
                ))}
              </div>
            </section>
          )}
        </div>
      </section>
    </main>
  );
}
