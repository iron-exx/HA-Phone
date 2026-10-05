import { describe, expect, it } from "vitest";
import { doorPatchBody, doorSchema, doorSummary } from "./doorSchema";

const VALID = { is_door: true, numeric_callerid: false, door_open_code: "*1", door_open_webhook: "", doorbell_camera: "" };

describe("doorSchema", () => {
  it("kürzt eingefügte Adressen um Leerzeichen", () => {
    const parsed = doorSchema.parse({ ...VALID, door_open_webhook: "  http://ha.local/api/webhook/tuer  " });
    expect(parsed.door_open_webhook).toBe("http://ha.local/api/webhook/tuer");
  });
  it("lehnt falsche Adressen und Codes ab", () => {
    expect(doorSchema.safeParse({ ...VALID, door_open_webhook: "ftp://x" }).success).toBe(false);
    expect(doorSchema.safeParse({ ...VALID, door_open_code: "12a" }).success).toBe(false);
    expect(doorSchema.safeParse({ ...VALID, doorbell_camera: "kamera" }).success).toBe(false);
  });
});

describe("doorPatchBody", () => {
  it("enthält nur Tür-Felder", () => {
    expect(Object.keys(doorPatchBody(VALID, [])).sort()).toEqual(
      ["door_actions", "door_open_code", "door_open_webhook", "doorbell_camera", "is_door", "numeric_callerid"],
    );
  });
});

describe("doorSummary", () => {
  it("beschreibt Öffner, Bild und Aktionen", () => {
    expect(doorSummary({ door_open_code: "*1", door_open_webhook: "", doorbell_camera: "camera.tuer", door_actions: [] }))
      .toBe("Öffnen mit *1 · mit Klingelbild");
    expect(doorSummary({ door_open_code: "", door_open_webhook: "http://x", doorbell_camera: "", door_actions: [{ label: "Licht", service: "light.turn_on", entity_id: "light.flur" }] }))
      .toBe("Öffnen per Schieberegler · ohne Klingelbild · 1 Aktion");
    expect(doorSummary({})).toBe("kein Tür-Öffner · ohne Klingelbild");
  });
});
