import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import App from "./App";
import { mockFetch, withStatus } from "./test/mockFetch";
import { renderAt } from "./test/render";

describe("App", () => {
  it("prüft die Sitzung, leitet /trunk um und markiert den Menüpunkt", async () => {
    mockFetch({ "/api/extensions": [] });
    renderAt(<App />, { route: "/trunk" });
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/connection/provider"));
    expect(await screen.findByRole("link", { name: "Telefonanbieter" })).toHaveAttribute("aria-current", "page");
  });

  it("schickt ohne Sitzung zur Anmeldung", async () => {
    mockFetch({ "/api/extensions": withStatus(401) });
    renderAt(<App />, { route: "/" });
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/login"));
  });

  it("setzt die dunkle Klasse nicht mehr fest", () => {
    mockFetch({});
    renderAt(<App />, { route: "/login" });
    expect(document.documentElement).not.toHaveClass("dark");
  });
});
