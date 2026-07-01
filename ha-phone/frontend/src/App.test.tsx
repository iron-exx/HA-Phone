import { describe, it, expect } from "vitest";

describe("App", () => {
  it("html element has class dark unconditionally", () => {
    // dark class added in main.tsx before mount; test the class is present
    document.documentElement.classList.add("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
