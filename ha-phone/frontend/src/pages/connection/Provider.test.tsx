import { describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import Provider from "./Provider";
import { callsTo, mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

describe("Telefonanbieter", () => {
  it("zeigt Zugangsdaten und weitere Rufnummern", async () => {
    mockFetch({ "/api/trunk/status": { status: "Registered" }, "/api/trunk/dids": [] });
    renderAt(<Provider />, { route: "/connection/provider" });
    expect(screen.getByRole("heading", { level: 1, name: "Telefonanbieter" })).toBeInTheDocument();
    expect(await screen.findByText("Weitere Rufnummern (Multi-DID)")).toBeInTheDocument();
    expect(await screen.findByText("Verbunden")).toBeInTheDocument();
  });

  it("zeigt Pflichtfeld-Fehler statt zu speichern", async () => {
    const fetchMock = mockFetch({ "/api/trunk/status": { status: "Registered" }, "/api/trunk/dids": [] });
    renderAt(<Provider />, { route: "/connection/provider" });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(screen.getAllByText("Pflichtfeld").length).toBeGreaterThan(0));
    expect(callsTo(fetchMock, "POST", "/api/trunk")).toHaveLength(0);
  });
});
