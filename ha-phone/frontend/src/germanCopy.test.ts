import { describe, expect, it } from "vitest";

// Alle Seiten und Komponenten (ohne Tests).
const SOURCES = import.meta.glob(["./pages/**/*.tsx", "./components/**/*.tsx", "!./**/*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const FORBIDDEN: RegExp[] = [
  />\s*(Add|Edit|Delete|Save|Cancel|Actions|Keep|Saving|Loading|Messages|Greeting|Custom|Default)\b/,
  /"(Required|Saved\.|Saving\.\.\.|Actions|Delete|Keep)"/,
  /Failed to /,
  /\bNo (routes|time conditions|messages)\b/i,
  /Time Condition/,
  /\b(Edit|Delete|Actions for) (Route|Time)/,
  /Max \d+ chars/,
  /Min \d+ characters/,
  /Max \d+ Zeichen/,
  /z\.B\./,
  /\be\.g\./,
  /Check that the PBX/,
  /(>|")\s*(Bitte ein |Neues )?Templates?( auswählen…?)?\s*(<|"|\.)|Neues Template|Template-Name|Template (gespeichert|gelöscht)|des Templates/,
];

describe("Deutsche Oberfläche", () => {
  it("findet Quelldateien", () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(0);
  });
  it.each(Object.entries(SOURCES))("%s enthält keine englischen UI-Reste", (_file, source) => {
    for (const pattern of FORBIDDEN) expect(source).not.toMatch(pattern);
  });
});
