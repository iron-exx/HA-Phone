import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { ThemeProvider } from "./ThemeProvider";
import { useTheme } from "@/lib/themeContext";
import { THEME_STORAGE_KEY } from "@/lib/theme";

function Probe() {
  const { preference, resolved, setPreference } = useTheme();
  return (
    <div>
      <output data-testid="pref">{preference}</output>
      <output data-testid="resolved">{resolved}</output>
      <button type="button" onClick={() => setPreference("light")}>hell</button>
    </div>
  );
}

function stubSystem(initialDark: boolean) {
  const listeners = new Set<(e: MediaQueryListEvent) => void>();
  const mq = {
    matches: initialDark,
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addEventListener: (_type: string, l: (e: MediaQueryListEvent) => void) => listeners.add(l),
    removeEventListener: (_type: string, l: (e: MediaQueryListEvent) => void) => listeners.delete(l),
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  };
  vi.stubGlobal("matchMedia", () => mq);
  return {
    emit(dark: boolean) {
      mq.matches = dark;
      listeners.forEach((l) => l({ matches: dark } as MediaQueryListEvent));
    },
  };
}

describe("ThemeProvider", () => {
  it("folgt dem System und reagiert auf einen Wechsel", () => {
    const system = stubSystem(true);
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(document.documentElement).toHaveClass("dark");
    act(() => system.emit(false));
    expect(document.documentElement).not.toHaveClass("dark");
    expect(screen.getByTestId("resolved")).toHaveTextContent("light");
  });

  it("die Wahl im Konto überstimmt das System und wird gespeichert", () => {
    stubSystem(true);
    render(<ThemeProvider><Probe /></ThemeProvider>);
    fireEvent.click(screen.getByRole("button", { name: "hell" }));
    expect(document.documentElement).not.toHaveClass("dark");
    expect(screen.getByTestId("pref")).toHaveTextContent("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });
});
