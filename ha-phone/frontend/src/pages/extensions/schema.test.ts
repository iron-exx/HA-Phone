import { describe, expect, it } from "vitest";
import { editDefaults, editPatchBody } from "./schema";

const EXT = { id: 1, number: 11, display_name: "Sandro", enabled: true, is_door: true, door_open_code: "*1", mobile_fallback: " 0171 5551234 " };

describe("editPatchBody", () => {
  it("sendet keine Tür-Felder (die gehören der Türklingel-Seite)", () => {
    const body = editPatchBody(editDefaults(EXT));
    for (const key of ["is_door", "door_open_code", "door_open_webhook", "doorbell_camera", "door_actions"]) {
      expect(body).not.toHaveProperty(key);
    }
  });
  it("sendet genau die erwarteten Schlüssel (mit Passwort ein Schlüssel mehr)", () => {
    const values = editDefaults(EXT);
    const base = [
      "display_name", "enabled", "ha_person", "internal_only", "mobile_fallback",
      "numeric_callerid", "presence_status", "recording_allowed", "video_capable",
    ];
    expect(Object.keys(editPatchBody(values)).sort()).toEqual(base);
    expect(Object.keys(editPatchBody({ ...values, sip_password: "geheim123" })).sort()).toEqual([...base, "sip_password"].sort());
  });
  it("kürzt Eingaben und sendet das Passwort nur, wenn eins eingegeben wurde", () => {
    const values = editDefaults(EXT);
    expect(editPatchBody(values).mobile_fallback).toBe("0171 5551234");
    expect(editPatchBody(values)).not.toHaveProperty("sip_password");
    expect(editPatchBody({ ...values, sip_password: "geheim123" }).sip_password).toBe("geheim123");
  });
});
