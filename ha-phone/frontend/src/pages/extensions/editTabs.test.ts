import { describe, expect, it } from "vitest";
import { firstTabWithError, isExtensionTab } from "./editTabs";

describe("firstTabWithError", () => {
  it("liefert den ersten Reiter mit Fehler in Reiter-Reihenfolge", () => {
    expect(firstTabWithError({ mobile_fallback: { type: "pattern", message: "x" } })).toBe("reach");
    expect(firstTabWithError({ mobile_fallback: { type: "pattern" }, display_name: { type: "min" } })).toBe("general");
    expect(firstTabWithError({ video_capable: { type: "x" } })).toBe("app");
    expect(firstTabWithError({})).toBeNull();
  });
  it("erkennt gültige Reiter-Werte", () => {
    expect(isExtensionTab("reach")).toBe(true);
    expect(isExtensionTab("tuer")).toBe(false);
  });
});
