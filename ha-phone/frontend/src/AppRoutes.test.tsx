import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import AppRoutes from "./AppRoutes";
import { LEGACY_REDIRECTS, NAV_PATHS } from "./nav";
import { mockFetch } from "./test/mockFetch";
import { renderAt } from "./test/render";

const location = () => screen.getByTestId("location").textContent;

describe("AppRoutes", () => {
  it.each(Object.entries(LEGACY_REDIRECTS))("leitet die alte Route %s auf %s um", async (from, to) => {
    mockFetch({});
    renderAt(<AppRoutes />, { route: from });
    await waitFor(() => expect(location()).toBe(to));
  });

  it.each(NAV_PATHS)("zeigt %s ohne Umleitung", (path) => {
    mockFetch({});
    renderAt(<AppRoutes />, { route: path });
    expect(location()).toBe(path);
  });

  it("leitet unbekannte Pfade auf die Übersicht", async () => {
    mockFetch({});
    renderAt(<AppRoutes />, { route: "/gibt-es-nicht" });
    await waitFor(() => expect(location()).toBe("/"));
  });
});
