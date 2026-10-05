import { describe, expect, it } from "vitest";

const SOURCES = import.meta.glob(["./**/*.tsx", "!./**/*.test.tsx", "!./test/**"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const FORBIDDEN: RegExp[] = [
  /rgba\(/,
  /hsl\(/,
  /violet-\d/,
  /#7C3AED|#4F46E5|#8b5cf6|#A78BFA|#C4B5FD|#050814|#080c17|#0b0e1a/i,
  /bg-\[#/,
  /text-slate-\d/,
  /(bg|border)-white\/(\[|\d)/,
  /text-(emerald|amber|red|green)-\d/,
];

// `text-end` ist in Tailwind `text-align: end` (kein Farb-Token); das Farb-Token heißt `ended`.
const CLASHING_TOKEN = /(?<![\w-])(text|bg|border)-end(?![\w-])/;

describe("Keine festverdrahteten Farben", () => {
  it.each(Object.entries(SOURCES))("%s nutzt nur Tokens", (_file, source) => {
    for (const pattern of FORBIDDEN) expect(source).not.toMatch(pattern);
  });

  it.each(Object.entries(SOURCES))("%s nutzt kein kollidierendes Token (text-end)", (_file, source) => {
    expect(source).not.toMatch(CLASHING_TOKEN);
  });
});
