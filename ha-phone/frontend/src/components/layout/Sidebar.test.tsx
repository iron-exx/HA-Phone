import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import Sidebar from "./Sidebar";
import { NAV_GROUPS } from "@/nav";
import { renderAt } from "@/test/render";

describe("Sidebar", () => {
  it("zeigt jeden Bereich mit seinen Menüpunkten", () => {
    renderAt(<Sidebar />);
    for (const group of NAV_GROUPS) {
      if (group.label) expect(screen.getByRole("group", { name: group.label })).toBeInTheDocument();
      for (const item of group.items) {
        expect(screen.getByRole("link", { name: item.label })).toHaveAttribute("href", item.to);
      }
    }
  });

  it.each([
    ["/calls/schedules", "Zeiten & Feiertage"],
    ["/doorbell/cameras", "Kameras für die App"],
    ["/doorbell", "Türstationen & Verlauf"],
    ["/", "Übersicht"],
  ])("markiert auf %s genau „%s”", (route, label) => {
    renderAt(<Sidebar />, { route });
    const current = screen.getAllByRole("link").filter((l) => l.getAttribute("aria-current") === "page");
    expect(current.map((l) => l.textContent)).toEqual([label]);
  });
});
