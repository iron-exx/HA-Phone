import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { DoorSettingsDialog } from "./DoorSettingsDialog";
import { callsTo, jsonBody, mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";
import type { Extension } from "@/types/api";

const DOOR: Extension = {
  id: 6, number: 16, display_name: "Türklingel", enabled: true, is_door: true, numeric_callerid: false,
  door_open_code: "*1", door_open_webhook: "", doorbell_camera: "camera.haustuer", door_actions: [],
};

describe("DoorSettingsDialog", () => {
  it("speichert nur Tür-Felder, Adressen gekürzt", async () => {
    const fetchMock = mockFetch({
      "PATCH /api/extensions/6": (init?: RequestInit) => ({ ...DOOR, ...jsonBody(init ?? {}) }),
    });
    const onSaved = vi.fn();
    renderAt(<DoorSettingsDialog extension={DOOR} onClose={() => {}} onSaved={onSaved} />);
    fireEvent.change(screen.getByLabelText("Tür-Öffnen-Webhook"), { target: { value: "  http://ha.local/api/webhook/tuer  " } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    const body = jsonBody(callsTo(fetchMock, "PATCH", "/api/extensions/6")[0]);
    expect(Object.keys(body).sort()).toEqual(
      ["door_actions", "door_open_code", "door_open_webhook", "doorbell_camera", "is_door", "numeric_callerid"],
    );
    expect(body.door_open_webhook).toBe("http://ha.local/api/webhook/tuer");
  });

  it("zeigt Fehler und speichert nicht bei falscher Adresse", async () => {
    const fetchMock = mockFetch({});
    renderAt(<DoorSettingsDialog extension={DOOR} onClose={() => {}} onSaved={() => {}} />);
    fireEvent.change(screen.getByLabelText("Tür-Öffnen-Webhook"), { target: { value: "ftp://x" } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    expect(await screen.findByText("http:// oder https:// Adresse")).toBeInTheDocument();
    expect(callsTo(fetchMock, "PATCH", "/api/extensions/6")).toHaveLength(0);
  });
});
