import { describe, expect, it } from "vitest";

// Jeder Task, der Seiten in einen neuen Ordner zieht, ergänzt hier seinen Glob.
const SOURCES = import.meta.glob(["./pages/calls/**/*.tsx", "!./pages/calls/**/*.test.tsx", "./pages/doorbell/**/*.tsx", "!./pages/doorbell/**/*.test.tsx", "./pages/extensions/**/*.tsx", "!./pages/extensions/**/*.test.tsx", "./pages/devices/**/*.tsx", "!./pages/devices/**/*.test.tsx", "./pages/connection/**/*.tsx", "!./pages/connection/**/*.test.tsx", "./pages/system/**/*.tsx", "!./pages/system/**/*.test.tsx", "./pages/overview/**/*.tsx", "!./pages/overview/**/*.test.tsx", "./pages/Phonebook.tsx"], {
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
