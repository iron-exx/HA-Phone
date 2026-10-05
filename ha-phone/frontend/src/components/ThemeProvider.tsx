import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  applyTheme,
  darkQuery,
  readThemePreference,
  resolveTheme,
  writeThemePreference,
  type ThemePreference,
} from "@/lib/theme";
import { ThemeContext } from "@/lib/themeContext";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(readThemePreference);
  const [systemDark, setSystemDark] = useState<boolean>(() => darkQuery()?.matches ?? false);

  useEffect(() => {
    const mq = darkQuery();
    if (!mq) return;
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }
    mq.addListener(onChange); // ältere Safari-/Android-WebViews
    return () => mq.removeListener(onChange);
  }, []);

  const resolved = resolveTheme(preference, systemDark);

  useEffect(() => {
    applyTheme(resolved);
  }, [resolved]);

  const setPreference = useCallback((next: ThemePreference) => {
    writeThemePreference(next);
    setPreferenceState(next);
  }, []);

  const value = useMemo(() => ({ preference, resolved, setPreference }), [preference, resolved, setPreference]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
