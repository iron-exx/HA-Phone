import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import Inbound from "./Inbound";
import { mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

const TARGETS = { "/api/extensions": [], "/api/ring-groups": [], "/api/ivrs": [] };

describe("Eingehend", () => {
  it("zeigt den deutschen Leerzustand und die Hauptaktion", async () => {
    mockFetch({ ...TARGETS, "/api/routes": [] });
    renderAt(<Inbound />, { route: "/calls/inbound" });
    expect(await screen.findByText("Noch keine Rufnummern-Routen")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Eingehend" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Route anlegen" })).toBeInTheDocument();
  });

  it("listet Routen mit Aktionen auf Deutsch", async () => {
    mockFetch({ ...TARGETS, "/api/routes": [{ id: 1, did: "+4922222222", destination_type: "hangup", destination_id: 0 }] });
    renderAt(<Inbound />, { route: "/calls/inbound" });
    expect(await screen.findByText("+4922222222")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aktionen für Route +4922222222" })).toBeInTheDocument();
  });

  it("zeigt im Anlegen-Dialog Pflichtfeld-Fehler an, statt stumm zu bleiben", async () => {
    mockFetch({ ...TARGETS, "/api/routes": [] });
    renderAt(<Inbound />, { route: "/calls/inbound" });
    fireEvent.click(screen.getByRole("button", { name: "Route anlegen" }));
    fireEvent.click(await screen.findByRole("button", { name: "Route speichern" }));
    expect(await screen.findByText("Pflichtfeld")).toBeInTheDocument();
  });
});
