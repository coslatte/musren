import { useEffect, useState } from "react";
import {
  deleteCredential,
  getCredentialStatus,
  getHistoryLocation,
  saveCredential,
} from "../../api/jobs";
import { readThemeMode, saveThemeMode, type ThemeMode } from "../../theme";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The desktop command failed.";
}

export function SettingsPage() {
  const [configured, setConfigured] = useState(false);
  const [value, setValue] = useState("");
  const [revealed, setRevealed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [historyLocation, setHistoryLocation] = useState("");
  const [theme, setTheme] = useState<ThemeMode>(readThemeMode);

  useEffect(() => {
    void Promise.allSettled([getCredentialStatus(), getHistoryLocation()]).then(
      ([status, location]) => {
        if (status.status === "fulfilled") setConfigured(status.value);
        else setError(messageOf(status.reason));
        if (location.status === "fulfilled") setHistoryLocation(location.value);
        else setError(messageOf(location.reason));
      },
    );
  }, []);

  async function save(): Promise<void> {
    if (!value) {
      setError("Enter an AcoustID API key.");
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      setConfigured(await saveCredential(value));
      setMessage("Saved to the operating system credential store.");
    } catch (failure: unknown) {
      setError(messageOf(failure));
    } finally {
      setValue("");
      setRevealed(false);
      setSaving(false);
    }
  }

  async function remove(): Promise<void> {
    setError(null);
    setMessage(null);
    try {
      await deleteCredential();
      setConfigured(false);
      setMessage("Credential removed from the operating system store.");
    } catch (failure: unknown) {
      setError(messageOf(failure));
    }
  }

  return (
    <main className="main-content" id="main">
      <header className="topbar">
        <div>
          <p className="eyebrow">LOCAL CONFIGURATION</p>
          <h1>Settings</h1>
        </div>
      </header>
      <section className="workspace">
        <section className="settings-card">
          <p className="eyebrow">APPEARANCE</p>
          <h2>Theme</h2>
          <p>
            Applies to this desktop app on this device. System follows the operating
            system light or dark setting.
          </p>
          <div className="field-group">
            <label htmlFor="theme-mode">Color theme</label>
            <select
              id="theme-mode"
              value={theme}
              onChange={(event) => {
                const mode = event.currentTarget.value;
                if (mode === "light" || mode === "dark" || mode === "system") {
                  setTheme(mode);
                  saveThemeMode(mode);
                }
              }}
            >
              <option value="system">System</option>
              <option value="light">Light (Lotus)</option>
              <option value="dark">Dark (Wave)</option>
            </select>
          </div>
        </section>
        <section className="settings-card">
          <p className="eyebrow">CREDENTIALS</p>
          <h2>AcoustID API key</h2>
          <p>
            Saved in the system credential store shared with musren CLI and TUI. The
            full value is never shown after saving.
          </p>
          <p className="credential-status">
            Status:{" "}
            <strong>{configured ? "Configured · ••••••••" : "Not configured"}</strong>
          </p>
          <label htmlFor="acoustid-key">API key</label>
          <div className="secret-input-row">
            <input
              id="acoustid-key"
              type={revealed ? "text" : "password"}
              autoComplete="new-password"
              value={value}
              onChange={(event) => setValue(event.currentTarget.value)}
              disabled={saving}
            />
            <button
              type="button"
              className="button-secondary"
              onClick={() => setRevealed(!revealed)}
            >
              {revealed ? "Hide" : "Show"}
            </button>
            <button
              type="button"
              className="button-primary"
              disabled={saving || !value}
              onClick={() => void save()}
            >
              {saving ? "Saving…" : "Save key"}
            </button>
          </div>
          {configured && (
            <button type="button" className="text-button" onClick={() => void remove()}>
              Remove saved key
            </button>
          )}
          {error && (
            <p className="inline-error" role="alert">
              {error}
            </p>
          )}
          {message && <p role="status">{message}</p>}
        </section>
        <section className="settings-card">
          <p className="eyebrow">LOCAL DATA</p>
          <h2>Session history</h2>
          <p>
            History database:{" "}
            <code>{historyLocation || "Loading local storage path…"}</code>
          </p>
          <p>History is kept on this device and never contains credential values.</p>
        </section>
      </section>
    </main>
  );
}
