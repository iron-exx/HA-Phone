import { Link } from "react-router-dom";
import { BellRing, ImageOff } from "lucide-react";
import type { DoorbellEvent } from "@/types/api";
import { SectionCard } from "@/components/SectionCard";
import { StatusChip } from "@/components/StatusChip";
import { apiUrl } from "@/lib/apiUrl";
import { formatDoorTime } from "./overviewLogic";

export function RecentDoorCard({ events, now }: { events: DoorbellEvent[]; now: Date }) {
  return (
    <SectionCard
      icon={BellRing}
      tone="door"
      title="Zuletzt an der Tür"
      actions={<Link to="/doorbell" className="text-sm font-bold text-blue hover:underline">Alle anzeigen</Link>}
    >
      {events.length === 0 ? (
        <p className="text-sm text-muted-foreground">Heute und gestern hat niemand geklingelt.</p>
      ) : (
        <ul className="grid">
          {events.map((ev) => (
            <li key={ev.id} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-t border-hair py-2.5 first:border-t-0">
              <span className="grid h-10 w-14 place-items-center overflow-hidden rounded-[9px] bg-raised text-faint">
                {ev.has_image ? <img src={apiUrl(`/api/doorbell/${ev.id}/image`)} alt="" className="h-full w-full object-cover" /> : <ImageOff className="size-4" aria-hidden="true" />}
              </span>
              <div className="min-w-0">
                <b className="block text-sm">{ev.door_name || `Tür ${ev.door_number}`} · {formatDoorTime(ev.started_at, now)}</b>
                <span className="text-[12.5px] font-semibold text-muted-foreground">
                  {ev.answered_by ? `angenommen von ${ev.answered_by}` : "nicht angenommen"}
                </span>
              </div>
              {ev.answered_by ? <StatusChip tone="ok" dot>angenommen</StatusChip> : <StatusChip tone="door">verpasst</StatusChip>}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
