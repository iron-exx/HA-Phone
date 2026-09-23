import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DoorAction } from "@/types/api";

export const MAX_DOOR_ACTIONS = 4;

const SERVICE_RE = /^[a-z_]+\.[a-z_]+$/;
const ENTITY_RE = /^[a-z_]+\.[a-z0-9_]+$/;

/** Returns a German error for the first invalid action, or null when all are fine. */
export function doorActionsError(actions: DoorAction[]): string | null {
  for (const [i, a] of actions.entries()) {
    const n = i + 1;
    if (!a.label.trim() || a.label.length > 24) return `Aktion ${n}: Beschriftung 1–24 Zeichen`;
    if (!SERVICE_RE.test(a.service)) return `Aktion ${n}: Dienst wie light.turn_on`;
    if (!ENTITY_RE.test(a.entity_id)) return `Aktion ${n}: Entität wie light.hausflur`;
  }
  return null;
}

/**
 * Home Assistant buttons the HA-Phone App shows in calls with this door station
 * (e.g. "Licht" → light.turn_on light.hausflur). The app only ever sees the label.
 */
export function DoorActionsEditor({
  value,
  onChange,
}: {
  value: DoorAction[];
  onChange: (next: DoorAction[]) => void;
}) {
  const update = (index: number, patch: Partial<DoorAction>) =>
    onChange(value.map((a, i) => (i === index ? { ...a, ...patch } : a)));
  const error = doorActionsError(value);

  return (
    <div className="space-y-2">
      <Label>Home-Assistant-Aktionen (Türstation)</Label>
      <p className="text-xs text-muted-foreground">
        Tasten in der HA-Phone App während eines Anrufs mit dieser Türstation, z. B. Licht einschalten oder Garage öffnen.
      </p>
      {value.map((a, i) => (
        <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2" data-testid={`door-action-${i}`}>
          <Input aria-label="Beschriftung" placeholder="Licht" value={a.label} onChange={(e) => update(i, { label: e.target.value })} />
          <Input aria-label="Dienst" placeholder="light.turn_on" value={a.service} onChange={(e) => update(i, { service: e.target.value.trim() })} />
          <Input aria-label="Entität" placeholder="light.hausflur" value={a.entity_id} onChange={(e) => update(i, { entity_id: e.target.value.trim() })} />
          <Button type="button" variant="ghost" size="icon" aria-label="Aktion entfernen" onClick={() => onChange(value.filter((_, j) => j !== i))}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
      {error && <p className="text-xs text-destructive">{error}</p>}
      {value.length < MAX_DOOR_ACTIONS && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onChange([...value, { label: "", service: "", entity_id: "" }])}
        >
          <Plus className="mr-1 h-4 w-4" /> Aktion hinzufügen
        </Button>
      )}
    </div>
  );
}
