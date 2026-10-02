import { useMemo, useState } from "react";

export type SortDir = "asc" | "desc";
export type SortValue = string | number | boolean | null | undefined;

/** Natural, locale-aware compare: numbers numerically, "Nst 9" before "Nst 10", case-insensitive. */
export function compareSortValues(a: SortValue, b: SortValue): number {
  if (a == null || a === "") return b == null || b === "" ? 0 : 1; // empty values last
  if (b == null || b === "") return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  if (typeof a === "boolean" && typeof b === "boolean") return a === b ? 0 : a ? -1 : 1;
  return String(a).localeCompare(String(b), "de", { numeric: true, sensitivity: "base" });
}

/**
 * Table sorting by column: `columns` maps a column key to the value it sorts by.
 * Clicking the active column flips the direction; another column starts ascending.
 * Pass a stable `columns` object (module constant or useMemo).
 */
export function useSort<T, K extends string>(rows: T[], columns: Record<K, (row: T) => SortValue>, initial: NoInfer<K>) {
  const [state, setState] = useState<{ key: K; dir: SortDir }>({ key: initial, dir: "asc" });
  const sorted = useMemo(() => {
    const get = columns[state.key];
    const sign = state.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => sign * compareSortValues(get(a), get(b)));
  }, [rows, columns, state]);
  const toggle = (key: K) =>
    setState((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }));
  return { sorted, sortKey: state.key, sortDir: state.dir, toggle };
}
