import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import Devices from "./Devices";
import { mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

describe("Tischtelefone", () => {
  it("hat die Reiter Geräte und Vorlagen", async () => {
    mockFetch({
      "/api/provisioning/devices": [],
      "/api/provisioning/templates": [],
      "/api/extensions": [],
      "/api/extensions/status": [],
      "/api/diagnostics/overview": { extensions: [] },
    });
    renderAt(<Devices />, { route: "/devices" });
    expect(screen.getByRole("heading", { level: 1, name: "Tischtelefone" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Gerät hinzufügen" })).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Vorlagen" }), { button: 0 });
    expect(screen.getByRole("tab", { name: "Vorlagen" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByRole("button", { name: "Neue Vorlage" })).toBeInTheDocument();
  });
});
