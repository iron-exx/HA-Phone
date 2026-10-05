import { describe, expect, it, vi } from "vitest";
import { applyTheme, readThemePreference, resolveTheme, THEME_STORAGE_KEY, writeThemePreference } from "./theme";

describe("readThemePreference", () => {
  it("liefert system, wenn nichts gespeichert ist", () => {
    expect(readThemePreference()).toBe("system");
  });
  it("liefert die gespeicherte Wahl", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "dark");
    expect(readThemePreference()).toBe("dark");
  });
  it("ignoriert unbekannte Werte", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "lila");
    expect(readThemePreference()).toBe("system");
  });
  it("fällt auf system zurück, wenn localStorage wirft", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("gesperrt", "SecurityError");
    });
    expect(readThemePreference()).toBe("system");
  });
});

describe("writeThemePreference", () => {
  it("speichert hell/dunkel und entfernt den Eintrag bei system", () => {
    writeThemePreference("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    writeThemePreference("system");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
  });
  it("wirft nicht, wenn localStorage wirft", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("voll");
    });
    expect(() => writeThemePreference("dark")).not.toThrow();
  });
});

describe("resolveTheme", () => {
  it("folgt bei system dem Gerät", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });
  it("feste Wahl schlägt das Gerät", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
  it("behandelt fehlendes matchMedia als hell", () => {
    vi.stubGlobal("matchMedia", undefined);
    expect(resolveTheme("system")).toBe("light");
  });
});

describe("applyTheme", () => {
  it("setzt Klasse, data-theme und color-scheme", () => {
    applyTheme("dark");
    expect(document.documentElement).toHaveClass("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    applyTheme("light");
    expect(document.documentElement).not.toHaveClass("dark");
  });
});
