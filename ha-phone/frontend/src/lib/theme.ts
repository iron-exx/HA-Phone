export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "haphone.theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

function isPreference(value: unknown): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

/** Gespeicherte Wahl aus dem Konto; "system", wenn nichts Lesbares gespeichert ist. */
export function readThemePreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isPreference(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

export function writeThemePreference(preference: ThemePreference): void {
  try {
    if (preference === "system") window.localStorage.removeItem(THEME_STORAGE_KEY);
    else window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Privates Fenster / gesperrter Speicher: die Wahl gilt nur bis zum Neuladen.
  }
}

export function darkQuery(): MediaQueryList | null {
  try {
    return typeof window.matchMedia === "function" ? window.matchMedia(DARK_QUERY) : null;
  } catch {
    return null;
  }
}

export function resolveTheme(
  preference: ThemePreference,
  systemDark: boolean = darkQuery()?.matches ?? false,
): ResolvedTheme {
  if (preference === "system") return systemDark ? "dark" : "light";
  return preference;
}

export function applyTheme(theme: ResolvedTheme, root: HTMLElement = document.documentElement): void {
  root.classList.toggle("dark", theme === "dark");
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
}
