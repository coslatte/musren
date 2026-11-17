export type ThemeMode = "light" | "dark" | "system";

const STORAGE_KEY = "musren-desktop-theme";

export function readThemeMode(): ThemeMode {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : "system";
}

export function saveThemeMode(mode: ThemeMode): void {
  localStorage.setItem(STORAGE_KEY, mode);
  applyTheme(mode);
}

function applyTheme(mode: ThemeMode): void {
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const dark = mode === "dark" || (mode === "system" && systemDark);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

/** Applies the saved theme and follows the OS preference while in system mode. */
export function initTheme(): void {
  applyTheme(readThemeMode());
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => applyTheme(readThemeMode()));
}
