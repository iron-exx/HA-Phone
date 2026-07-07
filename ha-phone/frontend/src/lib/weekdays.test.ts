import { describe, expect, it } from "vitest";

import { formatDays, formatDaysReadable, parseDays, WEEKDAYS } from "./weekdays";

describe("parseDays", () => {
  it("parses a simple range", () => {
    expect(parseDays("mon-fri")).toEqual(new Set(["mon", "tue", "wed", "thu", "fri"]));
  });

  it("parses a comma-separated list", () => {
    expect(parseDays("mon,wed,fri")).toEqual(new Set(["mon", "wed", "fri"]));
  });

  it("parses mon-sun as every day", () => {
    expect(parseDays("mon-sun")).toEqual(new Set(WEEKDAYS));
  });

  it("parses a wraparound range (fri-mon spans the weekend)", () => {
    expect(parseDays("fri-mon")).toEqual(new Set(["fri", "sat", "sun", "mon"]));
  });

  it("parses a single day", () => {
    expect(parseDays("sat")).toEqual(new Set(["sat"]));
  });

  it("ignores malformed/unknown tokens instead of throwing", () => {
    expect(parseDays("mon,bogus,fri")).toEqual(new Set(["mon", "fri"]));
    expect(() => parseDays("")).not.toThrow();
    expect(parseDays("")).toEqual(new Set());
  });
});

describe("formatDays", () => {
  it("condenses a contiguous run into a range", () => {
    expect(formatDays(new Set(["mon", "tue", "wed", "thu", "fri"]))).toBe("mon-fri");
  });

  it("collapses every day to mon-sun", () => {
    expect(formatDays(new Set(WEEKDAYS))).toBe("mon-sun");
  });

  it("lists non-contiguous days individually", () => {
    expect(formatDays(new Set(["mon", "wed", "fri"]))).toBe("mon,wed,fri");
  });

  it("mixes a range with individual days", () => {
    expect(formatDays(new Set(["mon", "tue", "wed", "fri"]))).toBe("mon-wed,fri");
  });

  it("returns an empty string for no selection", () => {
    expect(formatDays(new Set())).toBe("");
  });

  it("round-trips through parseDays for every format it produces", () => {
    const cases: Array<Set<string>> = [
      new Set(["mon", "tue", "wed", "thu", "fri"]),
      new Set(["sat", "sun"]),
      new Set(["mon", "wed", "fri"]),
      new Set(WEEKDAYS),
    ];
    for (const days of cases) {
      const formatted = formatDays(days as Set<(typeof WEEKDAYS)[number]>);
      expect(parseDays(formatted)).toEqual(days);
    }
  });
});

describe("formatDaysReadable", () => {
  it("translates a range to German abbreviations", () => {
    expect(formatDaysReadable("mon-fri")).toBe("Mo-Fr");
  });

  it("translates a comma list", () => {
    expect(formatDaysReadable("sat,sun")).toBe("Sa,So");
  });

  it("leaves unknown tokens untouched instead of throwing", () => {
    expect(formatDaysReadable("bogus")).toBe("bogus");
  });
});
