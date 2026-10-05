import { createContext, useContext } from "react";
import type { ResolvedTheme, ThemePreference } from "./theme";

export interface ThemeContextValue {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setPreference: (preference: ThemePreference) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme braucht einen <ThemeProvider>");
  return ctx;
}
