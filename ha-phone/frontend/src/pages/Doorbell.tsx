import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { DoorOpen, ImageOff, RefreshCw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiErrorMessage } from "@/lib/apiError";

interface DoorbellEvent {
  id: number;
  door_number: number;
  door_name: string;
  started_at: string;
  ended_at: string | null;
  answered_by: string;
  door_opened: boolean;
  has_image: boolean;
}

const dateFmt = new Intl.DateTimeFormat("de-DE", {
  weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
});

export default function Doorbell() {
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

  useEffect(() => { load(); }, [load]);

  async function remove(ev: DoorbellEvent) {
    const resp = await fetch(`/api/doorbell/${ev.id}`, { method: "DELETE" });
    if (resp.ok) setEvents((list) => (list ?? []).filter((e) => e.id !== ev.id));
    else toast.error(await apiErrorMessage(resp, "Löschen fehlgeschlagen"));
  }

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-xl font-semibold">Türklingel</h1>
        <Button variant="outline" size="sm" onClick={load}><RefreshCw className="h-4 w-4" /> Aktualisieren</Button>
      </div>
      <p className="text-sm text-muted-foreground mb-6">
        Jedes Klingeln an einer Türstation der letzten 30 Tage. Das Foto kommt aus der „Klingelbild-Quelle“ der
        Türstation (Nebenstellen → Türstation bearbeiten).
      </p>

      {events === null ? (
        <Skeleton className="h-40" />
      ) : events.length === 0 ? (
        <Card><CardContent className="py-8 text-sm text-muted-foreground">Noch hat niemand geklingelt.</CardContent></Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {events.map((ev) => (
            <Card key={ev.id} className="overflow-hidden">
              <button type="button" className="block w-full aspect-video bg-muted" onClick={() => ev.has_image && setZoom(ev)}
                aria-label={ev.has_image ? "Foto vergrößern" : "Kein Foto"}>
                {ev.has_image ? (
                  <img src={`/api/doorbell/${ev.id}/image`} alt={`Klingeln ${ev.door_name}`} loading="lazy"
                    className="w-full h-full object-cover" />
                ) : (
                  <span className="flex h-full items-center justify-center text-muted-foreground">
                    <ImageOff className="h-6 w-6" />
                  </span>
                )}
              </button>
              <CardContent className="p-3 text-sm space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{ev.door_name || `Tür ${ev.door_number}`}</span>
                  <span className="text-muted-foreground">{dateFmt.format(new Date(ev.started_at))}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className={ev.answered_by ? "" : "text-red-600"}>
                    {ev.answered_by ? `angenommen von ${ev.answered_by}` : "verpasst"}
                    {ev.door_opened && <span className="ml-2 inline-flex items-center gap-1 text-green-600"><DoorOpen className="h-3.5 w-3.5" /> geöffnet</span>}
                  </span>
                  <Button variant="ghost" size="sm" onClick={() => remove(ev)} aria-label="Eintrag löschen">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {zoom && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => setZoom(null)}>
          <img src={`/api/doorbell/${zoom.id}/image`} alt="Klingelbild groß" className="max-h-full max-w-full rounded" />
        </div>
      )}
    </div>
  );
}
