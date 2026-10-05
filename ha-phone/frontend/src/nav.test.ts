import { describe, expect, it } from "vitest";
import { findNavEntry, LEGACY_REDIRECTS, NAV_GROUPS, NAV_PATHS } from "./nav";

describe("nav", () => {
  it("hat sechs Bereiche mit 19 eindeutigen Menüpunkten", () => {
    expect(NAV_GROUPS.map((g) => g.label)).toEqual([null, "Telefone & Personen", "Anrufe", "Türklingel", "Anschluss", "System"]);
    expect(NAV_PATHS).toHaveLength(19);
    expect(new Set(NAV_PATHS).size).toBe(19);
  });
  it("jede alte Route zeigt auf einen Menüpunkt", () => {
    for (const to of Object.values(LEGACY_REDIRECTS)) expect(NAV_PATHS).toContain(to);
  });
  it("findet Bereich und Punkt zu einem Pfad", () => {
    expect(findNavEntry("/calls/schedules")?.group.label).toBe("Anrufe");
    expect(findNavEntry("/calls/schedules")?.item.label).toBe("Zeiten & Feiertage");
    expect(findNavEntry("/")?.item.label).toBe("Übersicht");
    expect(findNavEntry("/gibt-es-nicht")).toBeNull();
  });
  it("jeder Menüpunkt hat eine Beschreibung", () => {
    for (const g of NAV_GROUPS) for (const i of g.items) expect(i.description.length).toBeGreaterThan(10);
  });
});
