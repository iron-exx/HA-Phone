import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { compareSortValues, useSort } from "./useSort";

describe("compareSortValues", () => {
  it("sorts naturally, numbers numerically and empty values last", () => {
    const names = ["Nst 10", "nst 9", "", "Büro"];
    expect([...names].sort(compareSortValues)).toEqual(["Büro", "nst 9", "Nst 10", ""]);
    expect([16, 12, 19, 13, 14].sort(compareSortValues)).toEqual([12, 13, 14, 16, 19]);
  });
});

describe("useSort", () => {
  const rows = [{ n: 15, name: "dect" }, { n: 12, name: "larissa" }, { n: 14, name: "Büro" }];
  const columns = { number: (r: { n: number }) => r.n, name: (r: { name: string }) => r.name };

  it("starts with the initial column ascending and flips on a second click", () => {
    const { result } = renderHook(() => useSort(rows, columns, "number"));
    expect(result.current.sorted.map((r) => r.n)).toEqual([12, 14, 15]);
    act(() => result.current.toggle("number"));
    expect(result.current.sorted.map((r) => r.n)).toEqual([15, 14, 12]);
    act(() => result.current.toggle("name"));
    expect(result.current.sorted.map((r) => r.name)).toEqual(["Büro", "dect", "larissa"]);
  });
});
