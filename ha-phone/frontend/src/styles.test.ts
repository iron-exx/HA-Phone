import { describe, expect, it } from "vitest";
import css from "./index.css?raw";

const BASE_TOKENS = ["ground", "surface", "raised", "high", "stroke", "hair", "text", "text-muted", "text-faint",
  "blue", "blue-soft", "answer", "answer-soft", "end", "end-soft", "door", "door-soft", "violet", "violet-soft",
  "brand-gradient", "brand-ink", "brand-title-gradient"];

describe("index.css", () => {
  it("bildet die shadcn-Farbnamen per @theme inline auf Tokens ab", () => {
    expect(css).toMatch(/@theme inline\s*\{/);
    for (const name of ["background", "foreground", "card", "popover", "primary", "muted", "muted-foreground", "border", "input", "ring", "destructive", "accent"]) {
      expect(css).toMatch(new RegExp(`--color-${name}:\\s*var\\(`));
    }
  });
  it("definiert jedes Token für hell und dunkel", () => {
    for (const t of BASE_TOKENS) {
      expect(css.match(new RegExp(`--${t}:`, "g"))?.length ?? 0).toBeGreaterThanOrEqual(2);
    }
  });
  it("hat keine !important-Overrides und keine Google Fonts", () => {
    expect(css).not.toMatch(/!important/);
    expect(css).not.toMatch(/fonts\.googleapis/);
  });
});
