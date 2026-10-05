import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { DoorOpen, History, ImageOff, RefreshCw, Trash2 } from "lucide-react";
import type { DoorbellEvent } from "@/types/api";
import { apiUrl } from "@/lib/apiUrl";
import { apiErrorMessage } from "@/lib/apiError";
import { SectionCard } from "@/components/SectionCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const dateFmt = new Intl.DateTimeFormat("de-DE", {
  weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
});

export function DoorbellHistory() {
  const [events, setEvents] = useState<DoorbellEvent[] | null>(null);
  const [zoom, setZoom] = useState<DoorbellEvent | null>(null);

  const load = useCallback(async () => {
    try {
      const resp = await fetch("/api/doorbell?limit=200");
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Laden fehlgeschlagen"));
      setEvents(await resp.json());
    } catch (e) {
      setEvents([]);
      toast.error((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function remove(ev: DoorbellEvent) {
    const resp = await fetch(`/api/doorbell/${ev.id}`, { method: "DELETE" });
    if (resp.ok) setEvents((list) => (list ?? []).filter((e) => e.id !== ev.id));
    else toast.error(await apiErrorMessage(resp, "Löschen fehlgeschlagen"));
  }

  return (
    <SectionCard
      icon={History}
      tone="door"
      title="Klingel-Verlauf"
      description="Jedes Klingeln der letzten 30 Tage. Das Foto kommt aus der Klingelbild-Quelle der Türstation."
      actions={<Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw />Aktualisieren</Button>}
    >
      {events === null ? (
        <Skeleton className="h-40" />
      ) : events.length === 0 ? (
        <p className="py-4 text-sm text-muted-foreground">Noch hat niemand geklingelt.</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {events.map((ev) => (
            <article key={ev.id} className="overflow-hidden rounded-card border border-hair bg-card">
              <button
                type="button"
                className="block aspect-video w-full bg-raised"
                onClick={() => ev.has_image && setZoom(ev)}
                aria-label={ev.has_image ? "Foto vergrößern" : "Kein Foto"}
              >
                {ev.has_image ? (
                  <img src={apiUrl(`/api/doorbell/${ev.id}/image`)} alt={`Klingeln ${ev.door_name}`} loading="lazy" className="h-full w-full object-cover" />
                ) : (
                  <span className="flex h-full items-center justify-center text-faint"><ImageOff className="size-6" /></span>
                )}
              </button>
              <div className="space-y-1 p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-bold">{ev.door_name || `Tür ${ev.door_number}`}</span>
                  <span className="text-muted-foreground">{dateFmt.format(new Date(ev.started_at))}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className={ev.answered_by ? "" : "font-bold text-end"}>
                    {ev.answered_by ? `angenommen von ${ev.answered_by}` : "verpasst"}
                    {ev.door_opened && (
                      <span className="ml-2 inline-flex items-center gap-1 text-answer"><DoorOpen className="size-3.5" />geöffnet</span>
                    )}
                  </span>
                  <Button variant="ghost" size="sm" onClick={() => void remove(ev)} aria-label="Eintrag löschen"><Trash2 /></Button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      {zoom && (
        <button type="button" aria-label="Foto schließen" className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" onClick={() => setZoom(null)}>
          <img src={apiUrl(`/api/doorbell/${zoom.id}/image`)} alt="Klingelbild groß" className="max-h-full max-w-full rounded-ctl" />
        </button>
      )}
    </SectionCard>
  );
}
