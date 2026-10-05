import type { RingGroup } from "@/types/api";
import { cn } from "@/lib/utils";
import { toggleRingGroupId } from "./ringGroupMembership";

/** Rufgruppen-Auswahl für Anlegen- und Bearbeiten-Dialog. */
export function RingGroupPicker({
  ringGroups,
  selectedIds,
  onChange,
}: {
  ringGroups: RingGroup[];
  selectedIds: number[];
  onChange: (ids: number[]) => void;
}) {
  if (ringGroups.length === 0) return null;
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-bold">Rufgruppen</legend>
      <div className="grid gap-2">
        {ringGroups.map((group) => {
          const selected = selectedIds.includes(group.id);
          return (
            <button
              key={group.id}
              type="button"
              aria-pressed={selected}
              onClick={() => onChange(toggleRingGroupId(selectedIds, group.id))}
              className={cn(
                "flex items-center justify-between rounded-ctl border px-3 py-2 text-left text-sm transition-colors",
                selected ? "border-blue bg-blue-soft text-foreground" : "border-hair bg-card text-muted-foreground hover:text-foreground",
              )}
            >
              <span className="font-bold">{group.name}</span>
              <span className="text-xs">{selected ? "Zugewiesen" : "Nicht zugewiesen"}</span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
