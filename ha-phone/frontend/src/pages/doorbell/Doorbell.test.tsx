import { describe, expect, it } from "vitest";
import { fireEvent, screen, within } from "@testing-library/react";
import Doorbell from "./Doorbell";
import { mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

const DOOR = { id: 6, number: 16, display_name: "Türklingel", enabled: true, is_door: true, door_open_code: "*1", door_open_webhook: "", doorbell_camera: "camera.haustuer", door_actions: [] };
const PHONE = { id: 1, number: 11, display_name: "Sandro", enabled: true, is_door: false };

describe("Türstationen & Verlauf", () => {
  it("enthält die Tür-Einstellungen", async () => {
    mockFetch({ "/api/extensions": [DOOR, PHONE], "/api/doorbell": [] });
    renderAt(<Doorbell />, { route: "/doorbell" });
    const card = await screen.findByRole("region", { name: "Türstationen" });
    expect(within(card).getByText("Öffnen mit *1 · mit Klingelbild")).toBeInTheDocument();
    fireEvent.click(await within(card).findByRole("button", { name: "Einstellungen für Türklingel" }));
    expect(await screen.findByLabelText("Tür-Öffnen-Code (DTMF)")).toHaveValue("*1");
  });

  it("richtet eine weitere Nebenstelle als Türstation ein", async () => {
    mockFetch({ "/api/extensions": [DOOR, PHONE], "/api/doorbell": [] });
    renderAt(<Doorbell />, { route: "/doorbell" });
    fireEvent.change(await screen.findByLabelText("Weitere Nebenstelle als Türstation einrichten"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Einrichten" }));
    expect(await screen.findByRole("switch", { name: "Türstation" })).toHaveAttribute("aria-checked", "true");
  });

  it("zeigt den Klingel-Verlauf", async () => {
    mockFetch({ "/api/extensions": [], "/api/doorbell": [] });
    renderAt(<Doorbell />, { route: "/doorbell" });
    expect(await screen.findByText("Noch hat niemand geklingelt.")).toBeInTheDocument();
  });
});
