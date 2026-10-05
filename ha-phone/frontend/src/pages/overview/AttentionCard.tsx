import { Link } from "react-router-dom";
import { Activity, CircleCheck, TriangleAlert } from "lucide-react";
import { SectionCard } from "@/components/SectionCard";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AttentionItem } from "./overviewLogic";

export type UpdateState = "idle" | "running" | "done";

const ROW_TONE: Record<AttentionItem["tone"], string> = {
  error: "bg-end-soft [&_svg]:text-end",
  warn: "bg-door-soft [&_svg]:text-door",
  info: "bg-blue-soft [&_svg]:text-blue",
};

export function AttentionCard({ items, updateState, onStartUpdate }: { items: AttentionItem[]; updateState: UpdateState; onStartUpdate: () => void }) {
  return (
    <SectionCard icon={Activity} title="Braucht Aufmerksamkeit">
      {items.length === 0 ? (
        <p className="flex items-center gap-2.5 rounded-[14px] bg-answer-soft px-3 py-2.5 text-[13px] font-semibold">
          <CircleCheck className="size-[18px] shrink-0 text-answer" aria-hidden="true" />Alles in Ordnung.
        </p>
      ) : (
        <ul className="grid gap-2">
          {items.map((item) => (
            <li key={item.id} className={cn("flex flex-wrap items-center gap-2.5 rounded-[14px] px-3 py-2.5 text-[13px] font-semibold", ROW_TONE[item.tone])}>
              <TriangleAlert className="size-[18px] shrink-0" aria-hidden="true" />
              <span className="min-w-0 flex-1">{item.to ? <Link to={item.to} className="hover:underline">{item.text}</Link> : item.text}</span>
              {item.id === "update" && (
                <Button size="sm" onClick={onStartUpdate} disabled={updateState !== "idle"}>
                  {updateState === "done" ? "Update läuft – das kann einen Moment dauern." : updateState === "running" ? "Startet…" : "Jetzt aktualisieren"}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
