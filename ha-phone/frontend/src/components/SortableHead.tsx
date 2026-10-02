import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { TableHead } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { SortDir } from "@/lib/useSort";

/** Column heading that sorts its table on click (see useSort). */
export function SortableHead<K extends string>({
  column, label, sortKey, sortDir, onSort, className, plain = false,
}: {
  column: K;
  label: string;
  sortKey: K;
  sortDir: SortDir;
  onSort: (column: K) => void;
  className?: string;
  /** Plain <th> for tables that don't use the ui/table components. */
  plain?: boolean;
}) {
  const active = sortKey === column;
  const Icon = !active ? ArrowUpDown : sortDir === "asc" ? ArrowUp : ArrowDown;
  const Cell = plain ? "th" : TableHead;
  return (
    <Cell className={className} aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}>
      <button
        type="button"
        onClick={() => onSort(column)}
        className={cn("inline-flex items-center gap-1 uppercase tracking-widest hover:text-foreground", active && "text-foreground")}
        title={`Nach ${label} sortieren`}
      >
        {label}
        <Icon className={cn("h-3 w-3", !active && "opacity-40")} />
      </button>
    </Cell>
  );
}
