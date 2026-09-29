import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Camera } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleSwitch } from "@/components/ToggleSwitch";
import { apiErrorMessage } from "@/lib/apiError";

interface Cam {
  entity_id: string;
  name: string;
}

const MAX_SHARED = 12;

/** Which Home Assistant cameras paired phones may show as extra previews. Nothing is
 *  shared by default, so private cameras (e.g. a baby monitor) never reach a phone. */
export function SharedCamerasCard() {
  const [haCams, setHaCams] = useState<Cam[] | null>(null);
  const [haError, setHaError] = useState("");
  const [shared, setShared] = useState<Cam[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const sharedResp = await fetch("/api/doorbell/preview-cameras");
        if (sharedResp.ok) setShared(await sharedResp.json());
        const haResp = await fetch("/api/doorbell/ha-cameras");
        if (!haResp.ok) throw new Error(await apiErrorMessage(haResp, "Kameras nicht geladen"));
        setHaCams(await haResp.json());
      } catch (e) {
        setHaError((e as Error).message);
        setHaCams([]);
      }
    })();
  }, []);

  // HA cameras first, then shared ones HA no longer knows (so they can be removed).
  const all: Cam[] = [
    ...(haCams ?? []),
    ...shared.filter((s) => !(haCams ?? []).some((c) => c.entity_id === s.entity_id)),
  ];
  const sharedOf = (id: string) => shared.find((s) => s.entity_id === id);

  function toggle(cam: Cam) {
    if (sharedOf(cam.entity_id)) setShared(shared.filter((s) => s.entity_id !== cam.entity_id));
    else if (shared.length >= MAX_SHARED) toast.error(`Höchstens ${MAX_SHARED} Kameras`);
    else setShared([...shared, { entity_id: cam.entity_id, name: cam.name }]);
  }

  function rename(id: string, name: string) {
    setShared(shared.map((s) => (s.entity_id === id ? { ...s, name } : s)));
  }

  async function save() {
    setSaving(true);
    try {
      const resp = await fetch("/api/doorbell/preview-cameras", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cameras: shared }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen"));
      setShared(await resp.json());
      toast.success("Kamera-Freigabe gespeichert");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="mb-6">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center gap-2 font-medium"><Camera className="h-4 w-4" /> Kameras für die App</div>
        <p className="text-sm text-muted-foreground">
          Diese Kameras aus Home Assistant dürfen die gekoppelten Handys als zusätzliche Vorschau zeigen (beim
          Klingeln und auf der Türkarte). Welche davon ein Handy wirklich anzeigt, stellt jeder in der App ein.
          Nicht freigegebene Kameras sieht kein Handy.
        </p>
        {haCams === null ? (
          <Skeleton className="h-16" />
        ) : (
          <>
            {haError && <p className="text-sm text-red-600">{haError}</p>}
            {all.length === 0 && !haError && (
              <p className="text-sm text-muted-foreground">Home Assistant hat keine Kameras (camera.*).</p>
            )}
            <ul className="divide-y">
              {all.map((cam) => {
                const s = sharedOf(cam.entity_id);
                return (
                  <li key={cam.entity_id} className="flex flex-wrap items-center gap-3 py-2">
                    <ToggleSwitch checked={!!s} ariaLabel={`${cam.name} freigeben`} onToggle={() => toggle(cam)} />
                    <span className="min-w-40 flex-1 text-sm">
                      {cam.name}
                      <span className="block text-xs text-muted-foreground">{cam.entity_id}</span>
                    </span>
                    {s && (
                      <Input className="w-56" value={s.name} maxLength={64} placeholder="Name in der App"
                        aria-label={`Name für ${cam.entity_id}`} onChange={(e) => rename(cam.entity_id, e.target.value)} />
                    )}
                  </li>
                );
              })}
            </ul>
            <Button size="sm" onClick={save} disabled={saving}>Speichern</Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
