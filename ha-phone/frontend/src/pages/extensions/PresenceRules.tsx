import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import type { Extension, IVRMenu, PresenceForwardingRule, RingGroup } from "@/types/api";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { DestinationField, formatDestination, type DestinationValue } from "@/components/DestinationField";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PRESENCE_STATUSES } from "./schema";

const DIRECTION_LABELS: Record<string, string> = { internal: "Intern", external: "Extern" };
const MODE_LABELS: Record<string, string> = {
  ring_then_dest: "Klingeln, dann weiterleiten",
  always_dest: "Sofort weiterleiten",
};
const ALLOWED_TYPES = ["extension", "ring_group", "ivr", "voicemail", "hangup"] as const;
const FIELD = "mt-1 flex h-9 w-full rounded-ctl border border-input bg-card px-3 py-1 text-sm text-foreground";

/**
 * Wohin ein Anruf an diese Nebenstelle geht, solange sie in einem bestimmten
 * Anwesenheits-Status ist (getrennt intern/extern). Ohne Regel: klingeln, dann eigene Mailbox.
 */
export function PresenceRules({ extensionId }: { extensionId: number }) {
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [ringGroups, setRingGroups] = useState<RingGroup[]>([]);
  const [ivrMenus, setIvrMenus] = useState<IVRMenu[]>([]);
  const [rules, setRules] = useState<PresenceForwardingRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(PRESENCE_STATUSES[0].value);
  const [direction, setDirection] = useState<"internal" | "external">("internal");
  const [mode, setMode] = useState<"ring_then_dest" | "always_dest">("ring_then_dest");
  const [ringTimeout, setRingTimeout] = useState("20");
  const [dest, setDest] = useState<DestinationValue>({ type: "voicemail", target: undefined });

  const load = useCallback(() => {
    Promise.all([
      fetch("/api/extensions").then((r) => r.json()),
      fetch("/api/ring-groups").then((r) => r.json()),
      fetch("/api/ivrs").then((r) => r.json()),
      fetch("/api/presence-rules").then((r) => r.json()),
    ])
      .then(([ext, rg, ivr, ruleData]: [Extension[], RingGroup[], IVRMenu[], PresenceForwardingRule[]]) => {
        setExtensions(ext);
        setRingGroups(rg);
        setIvrMenus(ivr);
        setRules(ruleData.filter((r) => r.extension_id === extensionId));
      })
      .catch(() => toast.error("Weiterleitungsregeln konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [extensionId]);

  useEffect(() => {
    load();
  }, [load]);

  async function addRule() {
    setSaving(true);
    try {
      const resp = await fetch("/api/presence-rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          extension_id: extensionId,
          status,
          direction,
          mode,
          dest_type: dest.type,
          dest_target: dest.target ?? 0,
          ring_timeout: Number(ringTimeout) || 20,
        }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen."));
      load();
      toast.success("Regel gespeichert.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Speichern fehlgeschlagen."));
    } finally {
      setSaving(false);
    }
  }

  async function deleteRule(id: number) {
    try {
      const resp = await fetch(`/api/presence-rules/${id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      setRules((rs) => rs.filter((r) => r.id !== id));
      toast.success("Regel gelöscht.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Löschen."));
    }
  }

  return (
    <section aria-labelledby="presence-rules-title" className="space-y-3 border-t border-hair pt-4">
      <div>
        <h3 id="presence-rules-title" className="font-display text-base font-extrabold">Weiterleitung nach Anwesenheit</h3>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          Ohne Regel klingelt die Nebenstelle wie gewohnt und geht dann auf ihre Mailbox.
        </p>
      </div>
      {loading ? (
        <Skeleton className="h-11 w-full" />
      ) : rules.length === 0 ? (
        <p className="text-sm text-muted-foreground">Keine Regel für diese Nebenstelle.</p>
      ) : (
        <ul className="divide-y divide-hair rounded-ctl border border-hair">
          {rules.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
              <span>
                <b>{PRESENCE_STATUSES.find((s) => s.value === r.status)?.label || r.status}</b>
                {" · "}{DIRECTION_LABELS[r.direction] || r.direction}
                {" · "}{MODE_LABELS[r.mode] || r.mode}
                {r.mode === "ring_then_dest" && <span className="text-muted-foreground"> ({r.ring_timeout} s)</span>}
                {" → "}{formatDestination({ type: r.dest_type, target: r.dest_target }, extensions, ringGroups, ivrMenus, "id")}
              </span>
              <Button type="button" variant="ghost" size="icon" className="size-8 text-destructive" aria-label="Regel löschen" onClick={() => void deleteRule(r.id)}>
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      )}
      {!loading && (
        <div className="grid grid-cols-1 gap-3 rounded-ctl border border-hair bg-raised p-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-xs font-semibold text-muted-foreground">Status
            <select value={status} onChange={(e) => setStatus(e.target.value)} className={FIELD}>
              {PRESENCE_STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </label>
          <label className="text-xs font-semibold text-muted-foreground">Richtung
            <select value={direction} onChange={(e) => setDirection(e.target.value as "internal" | "external")} className={FIELD}>
              <option value="internal">Intern</option>
              <option value="external">Extern</option>
            </select>
          </label>
          <label className="text-xs font-semibold text-muted-foreground">Verhalten
            <select value={mode} onChange={(e) => setMode(e.target.value as "ring_then_dest" | "always_dest")} className={FIELD}>
              <option value="ring_then_dest">Klingeln, dann weiterleiten</option>
              <option value="always_dest">Sofort weiterleiten</option>
            </select>
          </label>
          {mode === "ring_then_dest" && (
            <label className="text-xs font-semibold text-muted-foreground">Klingeldauer (Sekunden)
              <input type="number" min={1} value={ringTimeout} onChange={(e) => setRingTimeout(e.target.value)} className={FIELD} />
            </label>
          )}
          <div className="sm:col-span-2 lg:col-span-3">
            <DestinationField
              value={dest}
              onChange={setDest}
              allowedTypes={[...ALLOWED_TYPES]}
              extensions={extensions}
              ringGroups={ringGroups}
              ivrMenus={ivrMenus}
              keyBy="id"
              label="Zieltyp"
            />
          </div>
          <div className="sm:col-span-2 lg:col-span-3">
            <Button type="button" size="sm" onClick={() => void addRule()} disabled={saving}>{saving ? "Speichert…" : "Regel speichern"}</Button>
          </div>
        </div>
      )}
    </section>
  );
}
