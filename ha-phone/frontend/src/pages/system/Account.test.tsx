import { describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import Account from "./Account";
import { THEME_STORAGE_KEY } from "@/lib/theme";
import { callsTo, jsonBody, mockFetch, withStatus } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

function fill(pw: string, confirm: string, current = "aktuelles-passwort") {
  fireEvent.change(screen.getByLabelText("Aktuelles Passwort"), { target: { value: current } });
  fireEvent.change(screen.getByLabelText("Neues Passwort"), { target: { value: pw } });
  fireEvent.change(screen.getByLabelText("Neues Passwort wiederholen"), { target: { value: confirm } });
  fireEvent.click(screen.getByRole("button", { name: "Passwort ändern" }));
}

describe("Konto", () => {
  it("Darstellung: Wahl wird angewendet und gespeichert", () => {
    mockFetch({});
    renderAt(<Account />, { route: "/system/account" });
    expect(screen.getByRole("button", { name: "Wie das System" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Dunkel" }));
    expect(screen.getByRole("button", { name: "Dunkel" })).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement).toHaveClass("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("prüft Länge und Wiederholung, bevor etwas gesendet wird", async () => {
    const fetchMock = mockFetch({});
    renderAt(<Account />, { route: "/system/account" });
    fill("kurz", "kurz");
    expect(await screen.findByRole("alert")).toHaveTextContent("Mindestens 12 Zeichen.");
    fill("langes-passwort-1", "langes-passwort-2");
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Die beiden Eingaben stimmen nicht überein."),
    );
    expect(callsTo(fetchMock, "POST", "/api/auth/change-password")).toHaveLength(0);
  });

  it("verlangt das aktuelle Passwort", async () => {
    const fetchMock = mockFetch({});
    renderAt(<Account />, { route: "/system/account" });
    fill("ein-sehr-gutes-passwort", "ein-sehr-gutes-passwort", "");
    expect(await screen.findByRole("alert")).toHaveTextContent("Gib dein aktuelles Passwort ein.");
    expect(callsTo(fetchMock, "POST", "/api/auth/change-password")).toHaveLength(0);
  });

  it("ändert das Passwort über den vorhandenen Endpunkt und leert die Felder", async () => {
    const fetchMock = mockFetch({ "POST /api/auth/change-password": { ok: true } });
    renderAt(<Account />, { route: "/system/account" });
    fill("ein-sehr-gutes-passwort", "ein-sehr-gutes-passwort");
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/auth/change-password")).toHaveLength(1));
    expect(jsonBody(callsTo(fetchMock, "POST", "/api/auth/change-password")[0])).toEqual({
      current_password: "aktuelles-passwort",
      new_password: "ein-sehr-gutes-passwort",
    });
    await waitFor(() => expect(screen.getByLabelText("Neues Passwort")).toHaveValue(""));
    expect(screen.getByLabelText("Aktuelles Passwort")).toHaveValue("");
  });

  it("zeigt die Meldung der Anlage bei Ablehnung", async () => {
    mockFetch({ "POST /api/auth/change-password": withStatus(422, { detail: "Standardpasswort nicht erlaubt" }) });
    renderAt(<Account />, { route: "/system/account" });
    fill("changeme-changeme", "changeme-changeme");
    expect(await screen.findByRole("alert")).toHaveTextContent("Standardpasswort nicht erlaubt");
  });

  it("zeigt bei falschem aktuellem Passwort die Meldung der Anlage", async () => {
    mockFetch({ "POST /api/auth/change-password": withStatus(403, { detail: "Aktuelles Passwort ist falsch." }) });
    renderAt(<Account />, { route: "/system/account" });
    fill("ein-sehr-gutes-passwort", "ein-sehr-gutes-passwort", "falsch");
    expect(await screen.findByRole("alert")).toHaveTextContent("Aktuelles Passwort ist falsch.");
  });
});
