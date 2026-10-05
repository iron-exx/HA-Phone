import { useState } from "react";
import { BellRing, Settings2 } from "lucide-react";
import type { Extension } from "@/types/api";
import { SectionCard } from "@/components/SectionCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { doorSummary } from "./doorSchema";

export function DoorStationsCard({
  extensions,
  loading,
  onEdit,
}: {
  extensions: Extension[];
  loading: boolean;
  onEdit: (extension: Extension) => void;
}) {
  const doors = extensions.filter((e) => e.is_door);
  const candidates = extensions.filter((e) => !e.is_door);
  const [candidateId, setCandidateId] = useState("");

  function setUpCandidate() {
    const ext = candidates.find((e) => String(e.id) === candidateId);
    if (!ext) return;
    onEdit({ ...ext, is_door: true });
    setCandidateId("");
  }

  return (
    <SectionCard
      icon={BellRing}
      tone="door"
      title="Türstationen"
      description="Nebenstellen, die als Türklingel oder Türsprechstelle arbeiten. Nur sie erscheinen im Verlauf und klingeln in der App als Tür."
    >
      {loading ? (
        <Skeleton className="h-16 w-full" />
      ) : doors.length === 0 ? (
        <p className="text-sm text-muted-foreground">Noch keine Türstation eingerichtet.</p>
      ) : (
        <ul className="divide-y divide-hair">
          {doors.map((door) => (
            <li key={door.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <p className="font-bold">
                  <span className="font-display tabular-nums">{door.number}</span> · {door.display_name}
                </p>
                <p className="text-[12.5px] font-semibold text-muted-foreground">{doorSummary(door)}</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => onEdit(door)} aria-label={`Einstellungen für ${door.display_name}`}>
                <Settings2 />Einstellungen
              </Button>
            </li>
          ))}
        </ul>
      )}
      {!loading && candidates.length > 0 && (
        <div className="flex flex-wrap items-end gap-2 border-t border-hair pt-3">
          <label className="grid gap-1 text-[12.5px] font-semibold text-muted-foreground">
            Weitere Nebenstelle als Türstation einrichten
            <select
              value={candidateId}
              onChange={(e) => setCandidateId(e.target.value)}
              className="h-9 min-w-56 rounded-ctl border border-input bg-card px-3 text-sm text-foreground"
            >
              <option value="">Nebenstelle wählen…</option>
              {candidates.map((e) => (
                <option key={e.id} value={e.id}>{e.number} {e.display_name}</option>
              ))}
            </select>
          </label>
          <Button variant="outline" onClick={setUpCandidate} disabled={!candidateId}>Einrichten</Button>
        </div>
      )}
    </SectionCard>
  );
}
