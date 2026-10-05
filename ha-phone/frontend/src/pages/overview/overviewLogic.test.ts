import { describe, expect, it } from "vitest";
import { buildAttention, countToday, formatDoorTime, greeting, summaryLine, trunkLabel } from "./overviewLogic";

const NOW = new Date(2026, 9, 5, 10, 30);
const ev = (d: Date) => ({ id: 1, door_number: 16, door_name: "Tür", started_at: d.toISOString(), ended_at: null, answered_by: "", door_opened: false, has_image: false });

describe("greeting", () => {
  it.each([[6, "Guten Morgen"], [10, "Guten Morgen"], [11, "Guten Tag"], [17, "Guten Tag"], [18, "Guten Abend"], [2, "Guten Abend"]])(
    "%i Uhr → %s", (hour, text) => expect(greeting(new Date(2026, 9, 5, hour))).toBe(text),
  );
});

describe("Türzeiten", () => {
  it("zählt nur heutiges Klingeln", () => {
    expect(countToday([ev(new Date(2026, 9, 5, 8)), ev(new Date(2026, 9, 4, 23, 59)), ev(new Date(2026, 9, 5, 0, 1))], NOW)).toBe(2);
  });
  it("schreibt heute/gestern", () => {
    expect(formatDoorTime(new Date(2026, 9, 5, 10, 7).toISOString(), NOW)).toBe("heute 10:07");
    expect(formatDoorTime(new Date(2026, 9, 4, 22, 51).toISOString(), NOW)).toBe("gestern 22:51");
  });
});

describe("buildAttention", () => {
  const base = { trunkStatus: "Registered", extensions: [], online: new Set<string>(), statusKnown: true, regenFailures: [], updateLatest: null };
  it("meldet nichts, wenn alles läuft", () => expect(buildAttention(base)).toEqual([]));
  it("meldet den Anbieter, aber nicht im Zustand UNKNOWN", () => {
    expect(buildAttention({ ...base, trunkStatus: "Unreachable" })[0].text).toBe("Telefonanbieter: Nicht erreichbar.");
    expect(buildAttention({ ...base, trunkStatus: "UNKNOWN" })).toEqual([]);
  });
  it("listet höchstens drei abgemeldete aktive Nebenstellen, Rest zusammengefasst", () => {
    const extensions = [11, 12, 13, 14, 15, 16].map((n) => ({ number: n, display_name: `N${n}`, enabled: n !== 16 }));
    const items = buildAttention({ ...base, extensions, online: new Set(["11"]) });
    expect(items.map((i) => i.text)).toEqual([
      "Nst. 12 „N12“ ist nicht angemeldet.",
      "Nst. 13 „N13“ ist nicht angemeldet.",
      "Nst. 14 „N14“ ist nicht angemeldet.",
      "1 weitere Nebenstelle ist nicht angemeldet.",
    ]);
  });
  it("meldet keine Nebenstellen, solange der Status unbekannt ist", () => {
    expect(buildAttention({ ...base, statusKnown: false, extensions: [{ number: 11, display_name: "A", enabled: true }] })).toEqual([]);
  });
  it("meldet fehlgeschlagene Konfiguration und Updates", () => {
    const items = buildAttention({ ...base, regenFailures: [{ name: "pjsip", label: "SIP-Konfiguration" }], updateLatest: "0.7.160" });
    expect(items.map((i) => i.id)).toEqual(["regen-pjsip", "update"]);
  });
});

describe("Texte", () => {
  it("summaryLine", () => {
    expect(summaryLine(5, 7, 0)).toBe("Alles läuft. 5 von 7 Nebenstellen sind angemeldet.");
    expect(summaryLine(1, 1, 1)).toBe("1 Punkt braucht Aufmerksamkeit. 1 von 1 Nebenstelle ist angemeldet.");
  });
  it("trunkLabel", () => {
    expect(trunkLabel("Registered")).toBe("Verbunden");
    expect(trunkLabel("Seltsam")).toBe("Seltsam");
  });
});
